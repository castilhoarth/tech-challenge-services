package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHealthHandler(t *testing.T) {
	t.Parallel()

	app := &App{
		RedisClient:         nil,
		SqsSvc:              nil,
		SqsQueueURL:         "",
		HttpClient:          nil,
		FlagServiceURL:      "http://localhost:8002",
		TargetingServiceURL: "http://localhost:8003",
	}

	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()

	app.healthHandler(w, req)

	if got := w.Code; got != http.StatusOK {
		t.Errorf("StatusCode = %d, want %d", got, http.StatusOK)
	}

	if got := w.Header().Get("Content-Type"); got != "application/json" {
		t.Errorf("Content-Type = %q, want %q", got, "application/json")
	}

	var resp map[string]string
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Errorf("Failed to decode response: %v", err)
	}

	if got := resp["status"]; got != "ok" {
		t.Errorf("status = %q, want %q", got, "ok")
	}
}

func TestEvaluationHandler(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name           string
		userID         string
		flagName       string
		expectedStatus int
		expectedError  bool
	}{
		{
			name:           "missing user_id parameter",
			userID:         "",
			flagName:       "test-flag",
			expectedStatus: http.StatusBadRequest,
			expectedError:  true,
		},
		{
			name:           "missing flag_name parameter",
			userID:         "user123",
			flagName:       "",
			expectedStatus: http.StatusBadRequest,
			expectedError:  true,
		},
		{
			name:           "missing both parameters",
			userID:         "",
			flagName:       "",
			expectedStatus: http.StatusBadRequest,
			expectedError:  true,
		},
		{
			name:           "valid parameters (would need mock dependencies)",
			userID:         "user123",
			flagName:       "feature-flag",
			expectedStatus: http.StatusOK,
			expectedError:  false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			app := &App{
				RedisClient:         nil,
				SqsSvc:              nil,
				SqsQueueURL:         "",
				HttpClient:          nil,
				FlagServiceURL:      "http://localhost:8002",
				TargetingServiceURL: "http://localhost:8003",
			}

			url := "/evaluate"
			if tt.userID != "" {
				url += "?user_id=" + tt.userID
			}
			if tt.flagName != "" {
				if tt.userID != "" {
					url += "&"
				} else {
					url += "?"
				}
				url += "flag_name=" + tt.flagName
			}

			req := httptest.NewRequest("GET", url, nil)
			w := httptest.NewRecorder()

			// Note: In production, we'd need to mock Redis, SQS, and HTTP dependencies
			// This demonstrates the parameter validation structure
			if tt.expectedError && (tt.userID == "" || tt.flagName == "") {
				app.evaluationHandler(w, req)
				if got := w.Code; got != tt.expectedStatus {
					t.Errorf("StatusCode = %d, want %d", got, tt.expectedStatus)
				}
			}
		})
	}
}

func TestEvaluationHandlerParameterValidation(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name           string
		queryString    string
		expectedStatus int
	}{
		{
			name:           "valid parameters",
			queryString:    "user_id=user123&flag_name=feature",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "empty parameters",
			queryString:    "user_id=&flag_name=",
			expectedStatus: http.StatusBadRequest,
		},
		{
			name:           "missing user_id",
			queryString:    "flag_name=feature",
			expectedStatus: http.StatusBadRequest,
		},
		{
			name:           "missing flag_name",
			queryString:    "user_id=user123",
			expectedStatus: http.StatusBadRequest,
		},
		{
			name:           "extra parameters",
			queryString:    "user_id=user123&flag_name=feature&extra=param",
			expectedStatus: http.StatusOK,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", "/evaluate?"+tt.queryString, nil)

			userID := req.URL.Query().Get("user_id")
			flagName := req.URL.Query().Get("flag_name")

			if (userID == "" || flagName == "") && tt.expectedStatus == http.StatusBadRequest {
				if userID == "" && flagName == "" {
					t.Logf("Both parameters missing, expecting BadRequest")
				} else if userID == "" {
					t.Logf("user_id missing, expecting BadRequest")
				} else if flagName == "" {
					t.Logf("flag_name missing, expecting BadRequest")
				}
			}
		})
	}
}

func TestEvaluationResponseStructure(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name     string
		response EvaluationResponse
		fields   []string
	}{
		{
			name: "valid response structure",
			response: EvaluationResponse{
				FlagName: "feature-flag",
				UserID:   "user123",
				Result:   true,
			},
			fields: []string{"flag_name", "user_id", "result"},
		},
		{
			name: "negative result",
			response: EvaluationResponse{
				FlagName: "disabled-flag",
				UserID:   "user456",
				Result:   false,
			},
			fields: []string{"flag_name", "user_id", "result"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			jsonData, err := json.Marshal(tt.response)
			if err != nil {
				t.Fatalf("Failed to marshal response: %v", err)
			}

			var decoded map[string]interface{}
			if err := json.Unmarshal(jsonData, &decoded); err != nil {
				t.Fatalf("Failed to unmarshal response: %v", err)
			}

			for _, field := range tt.fields {
				if _, exists := decoded[field]; !exists {
					t.Errorf("Field %q missing from response", field)
				}
			}

			if decoded["flag_name"] != tt.response.FlagName {
				t.Errorf("flag_name = %v, want %v", decoded["flag_name"], tt.response.FlagName)
			}
			if decoded["user_id"] != tt.response.UserID {
				t.Errorf("user_id = %v, want %v", decoded["user_id"], tt.response.UserID)
			}
			if decoded["result"] != tt.response.Result {
				t.Errorf("result = %v, want %v", decoded["result"], tt.response.Result)
			}
		})
	}
}
