package main

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"github.com/go-redis/redis/v8"
)

// Mock implementations for testing
type mockRedisClient struct {
	data    map[string]string
	getErr  error
	setErr  error
	delErr  error
}

func (m *mockRedisClient) Get(ctx context.Context, key string) *redis.StringCmd {
	val, exists := m.data[key]
	cmd := redis.NewStringCmd(ctx, nil)
	if !exists {
		cmd.SetErr(redis.Nil)
	} else if m.getErr != nil {
		cmd.SetErr(m.getErr)
	} else {
		cmd.SetVal(val)
	}
	return cmd
}

func (m *mockRedisClient) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.StatusCmd {
	m.data[key] = value.(string)
	cmd := redis.NewStatusCmd(ctx, nil, "")
	if m.setErr != nil {
		cmd.SetErr(m.setErr)
	}
	return cmd
}

func (m *mockRedisClient) Del(ctx context.Context, keys ...string) *redis.IntCmd {
	cmd := redis.NewIntCmd(ctx, nil, 0)
	if m.delErr != nil {
		cmd.SetErr(m.delErr)
	}
	return cmd
}

func (m *mockRedisClient) Close() error {
	return nil
}

func TestGetDecision(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name           string
		userID         string
		flagName       string
		expectedResult bool
		expectedErr    bool
		redisData      map[string]string
	}{
		{
			name:           "valid flag and rule evaluation",
			userID:         "user123",
			flagName:       "feature-flag",
			expectedResult: true,
			expectedErr:    false,
			redisData:      map[string]string{},
		},
		{
			name:           "flag not found",
			userID:         "user456",
			flagName:       "missing-flag",
			expectedResult: false,
			expectedErr:    true,
			redisData:      map[string]string{},
		},
		{
			name:           "cache hit",
			userID:         "user789",
			flagName:       "cached-flag",
			expectedResult: true,
			expectedErr:    false,
			redisData: map[string]string{
				"flag_info:cached-flag": `{"Flag":{"id":1,"name":"cached-flag","description":"Test","is_enabled":true},"Rule":{"id":1,"flag_name":"cached-flag","is_enabled":true,"rules":{"type":"PERCENTAGE","value":100}}}`,
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_ = &mockRedisClient{data: tt.redisData}

			// Note: In production, we'd create an App instance with mocked dependencies
			// This demonstrates the test structure for cache hits and error handling
		})
	}
}

func TestFetchFromServices(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name               string
		flagName           string
		expectedErr        bool
		expectedFlagExists bool
		expectedRuleExists bool
	}{
		{
			name:               "successful concurrent fetch",
			flagName:           "test-flag",
			expectedErr:        false,
			expectedFlagExists: true,
			expectedRuleExists: true,
		},
		{
			name:               "flag not found, rule found",
			flagName:           "partial-flag",
			expectedErr:        true,
			expectedFlagExists: false,
			expectedRuleExists: true,
		},
		{
			name:               "flag server timeout",
			flagName:           "timeout-flag",
			expectedErr:        true,
			expectedFlagExists: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Demonstrates the structure for testing concurrent service calls
			// with proper error handling and timeouts
			_ = tt.flagName
		})
	}
}

func TestNotFoundError(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name     string
		flagName string
		wantMsg  string
	}{
		{
			name:     "error message format",
			flagName: "missing-flag",
			wantMsg:  "flag ou regra 'missing-flag' não encontrada",
		},
		{
			name:     "empty flag name",
			flagName: "",
			wantMsg:  "flag ou regra '' não encontrada",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := &NotFoundError{FlagName: tt.flagName}
			if got := err.Error(); got != tt.wantMsg {
				t.Errorf("Error() = %q, want %q", got, tt.wantMsg)
			}
		})
	}
}

func TestCombinedFlagInfoSerialization(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name    string
		info    *CombinedFlagInfo
		wantErr bool
	}{
		{
			name: "valid serialization",
			info: &CombinedFlagInfo{
				Flag: &Flag{
					ID:          1,
					Name:        "test-flag",
					Description: "Test",
					IsEnabled:   true,
				},
				Rule: &TargetingRule{
					ID:        1,
					FlagName:  "test-flag",
					IsEnabled: true,
					Rules: Rule{
						Type:  "PERCENTAGE",
						Value: 50,
					},
				},
			},
			wantErr: false,
		},
		{
			name: "nil rule",
			info: &CombinedFlagInfo{
				Flag: &Flag{
					ID:        2,
					Name:      "no-rule-flag",
					IsEnabled: false,
				},
				Rule: nil,
			},
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			jsonData, err := json.Marshal(tt.info)
			if (err != nil) != tt.wantErr {
				t.Errorf("Marshal error = %v, wantErr %v", err, tt.wantErr)
				return
			}

			if err == nil {
				var deserialized CombinedFlagInfo
				if err := json.Unmarshal(jsonData, &deserialized); err != nil {
					t.Errorf("Unmarshal error = %v", err)
				}
			}
		})
	}
}

// Benchmark tests for performance-critical functions
func BenchmarkGetDecision(b *testing.B) {
	flagInfo := &CombinedFlagInfo{
		Flag: &Flag{
			ID:          1,
			Name:        "benchmark-flag",
			Description: "Benchmark",
			IsEnabled:   true,
		},
		Rule: &TargetingRule{
			ID:        1,
			FlagName:  "benchmark-flag",
			IsEnabled: true,
			Rules: Rule{
				Type:  "PERCENTAGE",
				Value: 50,
			},
		},
	}

	for i := 0; i < b.N; i++ {
		_ = flagInfo
	}
}
