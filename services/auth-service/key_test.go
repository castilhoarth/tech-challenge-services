package main

import (
	"strings"
	"testing"
)

func TestGenerateAPIKey(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name       string
		wantErr    bool
		wantPrefix string
		wantLen    int
	}{
		{
			name:       "valid key generation",
			wantErr:    false,
			wantPrefix: "tm_key_",
			wantLen:    71, // "tm_key_" (7 chars) + 64 hex chars (32 bytes * 2)
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			key1, err := generateAPIKey()
			if (err != nil) != tt.wantErr {
				t.Errorf("generateAPIKey() error = %v, wantErr %v", err, tt.wantErr)
				return
			}

			if !strings.HasPrefix(key1, tt.wantPrefix) {
				t.Errorf("key prefix = %q, want %q", key1[:7], tt.wantPrefix)
			}

			if len(key1) != tt.wantLen {
				t.Errorf("key length = %d, want %d", len(key1), tt.wantLen)
			}

			// Verify uniqueness (generate two keys and ensure they're different)
			key2, _ := generateAPIKey()
			if key1 == key2 {
				t.Error("generateAPIKey() produced duplicate keys")
			}
		})
	}
}

func TestHashAPIKey(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name          string
		key           string
		wantHashLen   int
		shouldConsist bool
	}{
		{
			name:          "valid key hashing",
			key:           "tm_key_test123456",
			wantHashLen:   64, // SHA-256 hex string is 64 chars
			shouldConsist: true,
		},
		{
			name:          "empty string hashing",
			key:           "",
			wantHashLen:   64,
			shouldConsist: true,
		},
		{
			name:          "long key hashing",
			key:           strings.Repeat("a", 1000),
			wantHashLen:   64,
			shouldConsist: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			hash1 := hashAPIKey(tt.key)

			if len(hash1) != tt.wantHashLen {
				t.Errorf("hash length = %d, want %d", len(hash1), tt.wantHashLen)
			}

			// Verify consistency (hashing same key should produce same hash)
			if tt.shouldConsist {
				hash2 := hashAPIKey(tt.key)
				if hash1 != hash2 {
					t.Errorf("hashAPIKey() produced different hashes for same input")
				}
			}

			// Verify it's valid hex
			for _, ch := range hash1 {
				if !isValidHexChar(ch) {
					t.Errorf("hash contains invalid hex char: %c", ch)
				}
			}
		})
	}
}

func TestHashAPIKeyCollision(t *testing.T) {
	t.Parallel()

	// Test that different keys produce different hashes
	key1 := "tm_key_key1"
	key2 := "tm_key_key2"

	hash1 := hashAPIKey(key1)
	hash2 := hashAPIKey(key2)

	if hash1 == hash2 {
		t.Error("hashAPIKey() produced same hash for different keys (collision)")
	}
}

func isValidHexChar(ch rune) bool {
	return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f') || (ch >= 'A' && ch <= 'F')
}
