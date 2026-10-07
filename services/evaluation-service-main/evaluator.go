package main

import (
	"context"
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"sync"
	"time"
)

const (
	// Tempo de vida do cache em segundos
	CACHE_TTL = 30 * time.Second
)

// getDecision é o wrapper principal
func (a *App) getDecision(ctx context.Context, userID, flagName string) (bool, error) {
	// 1. Obter os dados da flag (do cache ou dos serviços)
	info, err := a.getCombinedFlagInfo(ctx, flagName)
	if err != nil {
		return false, err
	}

	// 2. Executar a lógica de avaliação
	return a.runEvaluationLogic(info, userID), nil
}

// getCombinedFlagInfo busca os dados no Redis, com fallback para os microsserviços
func (a *App) getCombinedFlagInfo(ctx context.Context, flagName string) (*CombinedFlagInfo, error) {
	cacheKey := fmt.Sprintf("flag_info:%s", flagName)

	// 1. Tentar buscar do Cache (Redis)
	val, err := a.RedisClient.Get(ctx, cacheKey).Result()
	if err == nil {
		// Cache HIT
		var info CombinedFlagInfo
		if err := json.Unmarshal([]byte(val), &info); err == nil {
			log.Println("Cache HIT")
			return &info, nil
		}
		// Se o unmarshal falhar, trata como cache miss
		log.Println("Erro ao desserializar cache")
	}

	log.Println("Cache MISS")
	// 2. Cache MISS - Buscar dos serviços
	info, err := a.fetchFromServices(ctx, flagName)
	if err != nil {
		return nil, err
	}

	// 3. Salvar no Cache
	jsonData, err := json.Marshal(info)
	if err == nil {
		if err := a.RedisClient.Set(ctx, cacheKey, jsonData, CACHE_TTL).Err(); err != nil {
			log.Println("Erro ao salvar item no cache")
		}
	}

	return info, nil
}

// fetchFromServices busca dados do flag-service e targeting-service concorrentemente
func (a *App) fetchFromServices(ctx context.Context, flagName string) (*CombinedFlagInfo, error) {
	var wg sync.WaitGroup
	wg.Add(2)

	var flagInfo *Flag
	var ruleInfo *TargetingRule
	var flagErr, ruleErr error

	// Goroutine 1: Buscar do flag-service
	go func() {
		defer wg.Done()
		flagInfo, flagErr = a.fetchFlag(ctx, flagName)
	}()

	// Goroutine 2: Buscar do targeting-service
	go func() {
		defer wg.Done()
		ruleInfo, ruleErr = a.fetchRule(ctx, flagName)
	}()

	wg.Wait()

	if flagErr != nil {
		return nil, flagErr
	}
	if ruleErr != nil {
		log.Println("Nenhuma regra de segmentação encontrada; usando padrão")
	}

	return &CombinedFlagInfo{
		Flag: flagInfo,
		Rule: ruleInfo,
	}, nil
}

// fetchFlag (função helper)
func (a *App) fetchFlag(ctx context.Context, flagName string) (*Flag, error) {
	url := fmt.Sprintf("%s/flags/%s", a.FlagServiceURL, flagName)

	apiKey := os.Getenv("SERVICE_API_KEY")
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil) // #nosec G704 -- service URLs are validated during startup.
	if err != nil {
		return nil, fmt.Errorf("erro ao criar requisição para flag-service: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+apiKey)

	resp, err := a.HttpClient.Do(req) // #nosec G704 -- request target uses the startup-validated service URL.
	if err != nil {
		return nil, fmt.Errorf("erro ao chamar flag-service: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, &NotFoundError{flagName}
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("flag-service retornou status %d", resp.StatusCode)
	}

	body, _ := ioutil.ReadAll(resp.Body)
	var flag Flag
	if err := json.Unmarshal(body, &flag); err != nil {
		return nil, fmt.Errorf("erro ao desserializar resposta do flag-service: %w", err)
	}
	return &flag, nil
}

func (a *App) fetchRule(ctx context.Context, flagName string) (*TargetingRule, error) {
	url := fmt.Sprintf("%s/rules/%s", a.TargetingServiceURL, flagName)
	apiKey := os.Getenv("SERVICE_API_KEY")                       // Usa a mesma chave
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil) // #nosec G704 -- service URLs are validated during startup.
	if err != nil {
		return nil, fmt.Errorf("erro ao criar requisição para targeting-service: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+apiKey)

	resp, err := a.HttpClient.Do(req) // #nosec G704 -- request target uses the startup-validated service URL.
	if err != nil {
		return nil, fmt.Errorf("erro ao chamar targeting-service: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, &NotFoundError{flagName} // Não é um erro fatal
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("targeting-service retornou status %d", resp.StatusCode)
	}

	body, _ := ioutil.ReadAll(resp.Body)
	var rule TargetingRule
	if err := json.Unmarshal(body, &rule); err != nil {
		return nil, fmt.Errorf("erro ao desserializar resposta do targeting-service: %w", err)
	}
	return &rule, nil
}

// runEvaluationLogic é onde a decisão é tomada
func (a *App) runEvaluationLogic(info *CombinedFlagInfo, userID string) bool {
	if info.Flag == nil || !info.Flag.IsEnabled {
		return false
	}

	if info.Rule == nil || !info.Rule.IsEnabled {
		return true
	}

	// 3. Processa a regra (só temos "PERCENTAGE" por enquanto)
	rule := info.Rule.Rules
	if rule.Type == "PERCENTAGE" {
		// Converte o 'value' (que é interface{}) para float64
		percentage, ok := rule.Value.(float64)
		if !ok {
			log.Println("Valor da regra de porcentagem não é numérico")
			return false
		}

		// Calcula o "bucket" do usuário (0-99)
		userBucket := getDeterministicBucket(userID + info.Flag.Name)

		if float64(userBucket) < percentage {
			return true
		}
	}

	return false
}

func getDeterministicBucket(input string) int {
	// SHA-256 fornece uma distribuição determinística sem usar algoritmo fraco.
	hash := sha256.Sum256([]byte(input))

	// Converte 4 bytes para um uint32
	val := binary.BigEndian.Uint32(hash[:4])

	// Retorna o módulo 100
	return int(val % 100)
}
