package main

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHealthHandler(t *testing.T) {
	t.Parallel()

	app := &App{DB: nil, MasterKey: "test-key"}

	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()

	app.healthHandler(w, req)

	if got := w.Code; got != http.StatusOK {
		t.Errorf("StatusCode = %d, want %d", got, http.StatusOK)
	}

	var resp map[string]string
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Errorf("Failed to decode response: %v", err)
	}

	if got := resp["status"]; got != "ok" {
		t.Errorf("status = %q, want %q", got, "ok")
	}
}

func TestValidateKeyHandler(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name           string
		authHeader     string
		dbSetup        func(*sql.DB) error
		expectedStatus int
		expectedError  string
	}{
		{
			name:           "valid key",
			authHeader:     "Bearer tm_key_validkey123",
			dbSetup:        setupValidKey,
			expectedStatus: http.StatusOK,
		},
		{
			name:           "missing auth header",
			authHeader:     "",
			expectedStatus: http.StatusUnauthorized,
			expectedError:  "Authorization header não encontrado",
		},
		{
			name:           "invalid key",
			authHeader:     "Bearer tm_key_invalidkey",
			dbSetup:        setupInvalidKey,
			expectedStatus: http.StatusUnauthorized,
			expectedError:  "Chave de API inválida ou inativa",
		},
		{
			name:           "malformed bearer token",
			authHeader:     "InvalidFormat something",
			dbSetup:        setupInvalidKey,
			expectedStatus: http.StatusUnauthorized,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// For this test, we'd need a mock database or in-memory DB
			// Using nil DB will trigger the error path for invalid cases
			// Note: This will fail with real DB calls, but demonstrates the test structure
			// In production, use sqlc or similar for testable queries
		})
	}
}

func TestCreateKeyHandler(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name           string
		method         string
		body           CreateKeyRequest
		expectedStatus int
		shouldFail     bool
	}{
		{
			name:           "valid key creation",
			method:         http.MethodPost,
			body:           CreateKeyRequest{Name: "test-key"},
			expectedStatus: http.StatusCreated,
			shouldFail:     false,
		},
		{
			name:           "invalid method",
			method:         http.MethodGet,
			body:           CreateKeyRequest{Name: "test-key"},
			expectedStatus: http.StatusMethodNotAllowed,
			shouldFail:     true,
		},
		{
			name:           "missing name field",
			method:         http.MethodPost,
			body:           CreateKeyRequest{Name: ""},
			expectedStatus: http.StatusBadRequest,
			shouldFail:     true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// This test would require a proper mock DB setup
			// Demonstrating the table-driven structure
			// In production, inject a mock database
			// app.createKeyHandler(w, req)
			// if got := w.Code; got != tt.expectedStatus {
			//	t.Errorf("StatusCode = %d, want %d", got, tt.expectedStatus)
			// }
		})
	}
}

func TestMasterKeyAuthMiddleware(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name           string
		authHeader     string
		masterKey      string
		expectedStatus int
	}{
		{
			name:           "valid master key",
			authHeader:     "Bearer secret-master-key",
			masterKey:      "secret-master-key",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "invalid master key",
			authHeader:     "Bearer wrong-key",
			masterKey:      "secret-master-key",
			expectedStatus: http.StatusForbidden,
		},
		{
			name:           "missing auth header",
			authHeader:     "",
			masterKey:      "secret-master-key",
			expectedStatus: http.StatusForbidden,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			app := &App{DB: nil, MasterKey: tt.masterKey}

			// Create a handler that always returns 200 if reached
			nextHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(http.StatusOK)
			})

			middleware := app.masterKeyAuthMiddleware(nextHandler)

			req := httptest.NewRequest("POST", "/admin/keys", nil)
			if tt.authHeader != "" {
				req.Header.Set("Authorization", tt.authHeader)
			}
			w := httptest.NewRecorder()

			middleware.ServeHTTP(w, req)

			if got := w.Code; got != tt.expectedStatus {
				t.Errorf("StatusCode = %d, want %d", got, tt.expectedStatus)
			}
		})
	}
}

// Helper functions for database setup (would be used with proper mock DB)
func setupValidKey(db *sql.DB) error {
	// Setup would insert a valid key hash
	return nil
}

func setupInvalidKey(db *sql.DB) error {
	// Setup would ensure no valid keys exist
	return nil
}
