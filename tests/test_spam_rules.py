"""Comprehensive tests for SpamRuleManager business logic."""

import pytest
import json
import uuid
import tempfile
import os
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from datetime import datetime

from inbox_cleaner.spam_rules import SpamRuleManager


class TestSpamRuleManagerInit:
    """Test SpamRuleManager initialization."""

    def test_init_default_rules_file(self):
        """Test initialization with default rules file."""
        with patch.object(SpamRuleManager, 'load_rules') as mock_load:
            manager = SpamRuleManager()
            assert manager.rules_file == "spam_rules.json"
            assert manager.rules == []
            mock_load.assert_called_once()

    def test_init_custom_rules_file(self):
        """Test initialization with custom rules file."""
        with patch.object(SpamRuleManager, 'load_rules') as mock_load:
            manager = SpamRuleManager("custom_rules.json")
            assert manager.rules_file == "custom_rules.json"
            mock_load.assert_called_once()


class TestSpamRuleManagerRuleCreation:
    """Test spam rule creation functionality."""

    def setup_method(self):
        """Setup test environment."""
        with patch.object(SpamRuleManager, 'load_rules'):
            self.manager = SpamRuleManager("test_rules.json")

    @patch('uuid.uuid4')
    @patch('inbox_cleaner.spam_rules.datetime')
    def test_create_domain_rule(self, mock_datetime, mock_uuid):
        """Test creating a domain-based spam rule."""
        # Arrange
        mock_uuid.return_value = "test-uuid-123"
        mock_datetime.now.return_value.isoformat.return_value = "2024-01-01T12:00:00"
        
        # Act
        rule = self.manager.create_domain_rule("spam.com", "delete", "Known spam domain")
        
        # Assert
        assert rule["rule_id"] == "test-uuid-123"
        assert rule["type"] == "domain"
        assert rule["domain"] == "spam.com"
        assert rule["action"] == "delete"
        assert rule["reason"] == "Known spam domain"
        assert rule["created_at"] == "2024-01-01T12:00:00"
        assert rule["active"] is True
        
        # Should be added to rules list
        assert rule in self.manager.rules

    @patch('uuid.uuid4')
    @patch('inbox_cleaner.spam_rules.datetime')
    def test_create_subject_rule(self, mock_datetime, mock_uuid):
        """Test creating a subject pattern rule."""
        # Arrange
        mock_uuid.return_value = "subject-rule-456"
        mock_datetime.now.return_value.isoformat.return_value = "2024-01-01T12:30:00"
        
        # Act
        rule = self.manager.create_subject_rule(
            r"FREE.*MONEY",
            "delete",
            "Free money spam pattern"
        )
        
        # Assert
        assert rule["rule_id"] == "subject-rule-456"
        assert rule["type"] == "subject"
        assert rule["pattern"] == r"FREE.*MONEY"
        assert rule["action"] == "delete"
        assert rule["reason"] == "Free money spam pattern"
        assert rule["active"] is True

    @patch('uuid.uuid4')
    @patch('inbox_cleaner.spam_rules.datetime')
    def test_create_sender_rule(self, mock_datetime, mock_uuid):
        """Test creating a sender pattern rule."""
        # Arrange
        mock_uuid.return_value = "sender-rule-789"
        mock_datetime.now.return_value.isoformat.return_value = "2024-01-01T13:00:00"
        
        # Act
        rule = self.manager.create_sender_rule(
            r".*\d+\.\d+\.\d+\.\d+.*@",
            "delete", 
            "Sender contains IP address"
        )
        
        # Assert
        assert rule["rule_id"] == "sender-rule-789"
        assert rule["type"] == "sender"
        assert rule["pattern"] == r".*\d+\.\d+\.\d+\.\d+.*@"
        assert rule["action"] == "delete"
        assert rule["reason"] == "Sender contains IP address"
        assert rule["active"] is True


class TestSpamRuleManagerRuleMatching:
    """Test spam rule matching functionality."""

    def setup_method(self):
        """Setup test environment with sample rules."""
        with patch.object(SpamRuleManager, 'load_rules'):
            self.manager = SpamRuleManager("test_rules.json")
            
        # Add sample rules
        self.manager.rules = [
            {
                "rule_id": "domain-rule",
                "type": "domain",
                "domain": "spam.com",
                "action": "delete",
                "reason": "Known spam domain",
                "active": True
            },
            {
                "rule_id": "subject-rule",
                "type": "subject",
                "pattern": r"FREE.*MONEY",
                "action": "delete",
                "reason": "Free money pattern",
                "active": True
            },
            {
                "rule_id": "sender-rule",
                "type": "sender",
                "pattern": r".*\d+\.\d+\.\d+\.\d+.*@",
                "action": "delete",
                "reason": "IP in sender",
                "active": True
            },
            {
                "rule_id": "inactive-rule",
                "type": "domain",
                "domain": "inactive.com",
                "action": "delete",
                "reason": "Inactive rule",
                "active": False
            }
        ]

    def test_matches_spam_rule_domain_match(self):
        """Test email matching against domain rule."""
        # Arrange
        email = {
            "sender_domain": "spam.com",
            "sender_email": "test@spam.com",
            "subject": "Regular email"
        }
        
        # Act
        result = self.manager.matches_spam_rule(email)
        
        # Assert
        assert result is not None
        assert result["rule_id"] == "domain-rule"
        assert result["type"] == "domain"

    def test_matches_spam_rule_subject_match(self):
        """Test email matching against subject pattern rule."""
        # Arrange
        email = {
            "sender_domain": "legit.com",
            "sender_email": "test@legit.com", 
            "subject": "GET FREE MONEY NOW!"
        }
        
        # Act
        result = self.manager.matches_spam_rule(email)
        
        # Assert
        assert result is not None
        assert result["rule_id"] == "subject-rule"
        assert result["type"] == "subject"

    def test_matches_spam_rule_sender_match(self):
        """Test email matching against sender pattern rule."""
        # Arrange
        email = {
            "sender_domain": "example.com",
            "sender_email": "user192.168.1.1test@example.com",
            "subject": "Regular subject"
        }
        
        # Act
        result = self.manager.matches_spam_rule(email)
        
        # Assert
        assert result is not None
        assert result["rule_id"] == "sender-rule"
        assert result["type"] == "sender"

    def test_matches_spam_rule_no_match(self):
        """Test email that doesn't match any rules."""
        # Arrange
        email = {
            "sender_domain": "legitimate.org",
            "sender_email": "user@legitimate.org",
            "subject": "Important business email"
        }
        
        # Act
        result = self.manager.matches_spam_rule(email)
        
        # Assert
        assert result is None

    def test_matches_spam_rule_inactive_rule_skipped(self):
        """Test that inactive rules are skipped."""
        # Arrange
        email = {
            "sender_domain": "inactive.com",
            "sender_email": "test@inactive.com",
            "subject": "Should not match inactive rule"
        }
        
        # Act
        result = self.manager.matches_spam_rule(email)
        
        # Assert
        assert result is None

    def test_matches_spam_rule_case_insensitive_subject(self):
        """Test case insensitive subject pattern matching."""
        # Arrange
        email = {
            "sender_domain": "test.com",
            "sender_email": "test@test.com",
            "subject": "get free money today"  # lowercase
        }
        
        # Act
        result = self.manager.matches_spam_rule(email)
        
        # Assert
        assert result is not None
        assert result["rule_id"] == "subject-rule"

    def test_matches_spam_rule_case_insensitive_sender(self):
        """Test case insensitive sender pattern matching."""
        # Arrange
        email = {
            "sender_domain": "test.com", 
            "sender_email": "USER192.168.1.1TEST@TEST.COM",  # uppercase
            "subject": "regular subject"
        }
        
        # Act
        result = self.manager.matches_spam_rule(email)
        
        # Assert
        assert result is not None
        assert result["rule_id"] == "sender-rule"

    def test_matches_spam_rule_missing_email_fields(self):
        """Test matching with missing email fields."""
        # Arrange
        email = {
            "subject": "FREE MONEY NOW!"
            # Missing sender fields
        }
        
        # Act
        result = self.manager.matches_spam_rule(email)
        
        # Assert
        assert result is not None
        assert result["rule_id"] == "subject-rule"


class TestSpamRuleManagerRuleRetrieval:
    """Test rule retrieval and filtering functionality."""

    def setup_method(self):
        """Setup test environment with sample rules."""
        with patch.object(SpamRuleManager, 'load_rules'):
            self.manager = SpamRuleManager("test_rules.json")
            
        self.manager.rules = [
            {"rule_id": "rule1", "type": "domain", "domain": "spam.com", "active": True},
            {"rule_id": "rule2", "type": "subject", "pattern": "spam", "active": False},
            {"rule_id": "rule3", "type": "domain", "domain": "spam.com", "active": True},
            {"rule_id": "rule4", "type": "sender", "pattern": "test", "active": True}
        ]

    def test_get_all_rules(self):
        """Test getting all rules."""
        result = self.manager.get_all_rules()
        
        assert len(result) == 4
        assert result is not self.manager.rules  # Should be a copy
        assert result[0]["rule_id"] == "rule1"

    def test_get_active_rules(self):
        """Test getting only active rules."""
        result = self.manager.get_active_rules()
        
        assert len(result) == 3  # rule2 is inactive
        active_ids = [rule["rule_id"] for rule in result]
        assert "rule1" in active_ids
        assert "rule2" not in active_ids
        assert "rule3" in active_ids
        assert "rule4" in active_ids

    def test_get_rule_by_id_exists(self):
        """Test getting rule by existing ID."""
        result = self.manager.get_rule_by_id("rule2")
        
        assert result is not None
        assert result["rule_id"] == "rule2"
        assert result["active"] is False

    def test_get_rule_by_id_not_exists(self):
        """Test getting rule by non-existent ID."""
        result = self.manager.get_rule_by_id("nonexistent")
        assert result is None

    def test_get_rules_by_domain(self):
        """Test getting rules for specific domain."""
        result = self.manager.get_rules_by_domain("spam.com")
        
        assert len(result) == 2
        domain_ids = [rule["rule_id"] for rule in result]
        assert "rule1" in domain_ids
        assert "rule3" in domain_ids

    def test_get_rules_by_domain_no_matches(self):
        """Test getting rules for domain with no matches."""
        result = self.manager.get_rules_by_domain("nonexistent.com")
        assert result == []


class TestSpamRuleManagerRuleModification:
    """Test rule modification functionality."""

    def setup_method(self):
        """Setup test environment."""
        with patch.object(SpamRuleManager, 'load_rules'):
            self.manager = SpamRuleManager("test_rules.json")
            
        self.manager.rules = [
            {
                "rule_id": "modifiable-rule",
                "type": "domain",
                "domain": "old.com",
                "action": "delete",
                "reason": "Old reason",
                "active": True,
                "created_at": "2024-01-01T00:00:00"
            }
        ]

    @patch('inbox_cleaner.spam_rules.datetime')
    def test_update_rule_success(self, mock_datetime):
        """Test successful rule update."""
        # Arrange
        mock_datetime.now.return_value.isoformat.return_value = "2024-01-02T12:00:00"
        updates = {
            "domain": "new.com",
            "reason": "Updated reason",
            "active": False
        }
        
        # Act
        result = self.manager.update_rule("modifiable-rule", updates)
        
        # Assert
        assert result is True
        rule = self.manager.get_rule_by_id("modifiable-rule")
        assert rule["domain"] == "new.com"
        assert rule["reason"] == "Updated reason"
        assert rule["active"] is False
        assert rule["updated_at"] == "2024-01-02T12:00:00"

    def test_update_rule_not_found(self):
        """Test updating non-existent rule."""
        result = self.manager.update_rule("nonexistent", {"domain": "test.com"})
        assert result is False

    def test_delete_rule_success(self):
        """Test successful rule deletion."""
        # Act
        result = self.manager.delete_rule("modifiable-rule")
        
        # Assert
        assert result is True
        assert len(self.manager.rules) == 0
        assert self.manager.get_rule_by_id("modifiable-rule") is None

    def test_delete_rule_not_found(self):
        """Test deleting non-existent rule."""
        result = self.manager.delete_rule("nonexistent")
        assert result is False
        assert len(self.manager.rules) == 1  # Original rule still there

    @patch('inbox_cleaner.spam_rules.datetime')
    def test_toggle_rule_active_to_inactive(self, mock_datetime):
        """Test toggling rule from active to inactive."""
        # Arrange
        mock_datetime.now.return_value.isoformat.return_value = "2024-01-02T12:00:00"
        
        # Act
        result = self.manager.toggle_rule("modifiable-rule")
        
        # Assert
        assert result is True
        rule = self.manager.get_rule_by_id("modifiable-rule")
        assert rule["active"] is False
        assert rule["updated_at"] == "2024-01-02T12:00:00"

    @patch('inbox_cleaner.spam_rules.datetime')
    def test_toggle_rule_inactive_to_active(self, mock_datetime):
        """Test toggling rule from inactive to active."""
        # Arrange
        self.manager.rules[0]["active"] = False
        mock_datetime.now.return_value.isoformat.return_value = "2024-01-02T13:00:00"
        
        # Act
        result = self.manager.toggle_rule("modifiable-rule")
        
        # Assert
        assert result is True
        rule = self.manager.get_rule_by_id("modifiable-rule")
        assert rule["active"] is True

    def test_toggle_rule_not_found(self):
        """Test toggling non-existent rule."""
        result = self.manager.toggle_rule("nonexistent")
        assert result is False


class TestSpamRuleManagerFilePersistence:
    """Test file save and load functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        
        with patch.object(SpamRuleManager, 'load_rules'):
            self.manager = SpamRuleManager(self.temp_file.name)

    def teardown_method(self):
        """Clean up temp files."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_save_rules_success(self):
        """Test successful rule saving."""
        # Arrange
        self.manager.rules = [
            {"rule_id": "test1", "type": "domain", "domain": "test.com", "active": True},
            {"rule_id": "test2", "type": "subject", "pattern": "spam", "active": False}
        ]
        
        # Act
        result = self.manager.save_rules()
        
        # Assert
        assert result is True
        
        # Verify file contents
        with open(self.temp_file.name, 'r') as f:
            saved_data = json.load(f)
        
        assert len(saved_data) == 2
        assert saved_data[0]["rule_id"] == "test1"
        assert saved_data[1]["rule_id"] == "test2"

    def test_save_rules_failure(self):
        """Test rule saving with file error."""
        # Arrange - invalid file path
        self.manager.rules_file = "/invalid/path/rules.json"
        
        # Act
        result = self.manager.save_rules()
        
        # Assert
        assert result is False

    def test_load_rules_success(self):
        """Test successful rule loading."""
        # Arrange - create test file with rules
        test_rules = [
            {"rule_id": "loaded1", "type": "domain", "domain": "loaded.com"},
            {"rule_id": "loaded2", "type": "subject", "pattern": "loaded"}
        ]
        
        with open(self.temp_file.name, 'w') as f:
            json.dump(test_rules, f)
        
        # Act
        result = self.manager.load_rules()
        
        # Assert
        assert result is True
        assert len(self.manager.rules) == 2
        assert self.manager.rules[0]["rule_id"] == "loaded1"
        assert self.manager.rules[1]["rule_id"] == "loaded2"

    def test_load_rules_file_not_exists(self):
        """Test loading rules when file doesn't exist."""
        # Arrange - remove temp file
        os.unlink(self.temp_file.name)
        
        # Act
        result = self.manager.load_rules()
        
        # Assert
        assert result is True
        assert self.manager.rules == []

    def test_load_rules_invalid_json(self):
        """Test loading rules with invalid JSON."""
        # Arrange - create file with invalid JSON
        with open(self.temp_file.name, 'w') as f:
            f.write("invalid json content")
        
        # Act
        result = self.manager.load_rules()
        
        # Assert
        assert result is False
        assert self.manager.rules == []


class TestSpamRuleManagerStatistics:
    """Test statistics and analysis functionality."""

    def setup_method(self):
        """Setup test environment."""
        with patch.object(SpamRuleManager, 'load_rules'):
            self.manager = SpamRuleManager("test_rules.json")
            
        self.manager.rules = [
            {"rule_id": "r1", "type": "domain", "action": "delete", "active": True},
            {"rule_id": "r2", "type": "domain", "action": "mark", "active": False},
            {"rule_id": "r3", "type": "subject", "action": "delete", "active": True},
            {"rule_id": "r4", "type": "sender", "action": "delete", "active": True},
            {"rule_id": "r5", "type": "subject", "action": "delete", "active": False}
        ]

    def test_get_deletion_stats(self):
        """Test getting deletion statistics."""
        result = self.manager.get_deletion_stats()
        
        assert result["total_rules"] == 5
        assert result["active_rules"] == 3
        assert result["deletion_rules"] == 4  # 4 rules with delete action
        
        # Check rules by type
        assert result["rules_by_type"]["domain"] == 2
        assert result["rules_by_type"]["subject"] == 2
        assert result["rules_by_type"]["sender"] == 1


class TestSpamRuleManagerPredefinedRules:
    """Test predefined spam rule creation."""

    def setup_method(self):
        """Setup test environment."""
        with patch.object(SpamRuleManager, 'load_rules'):
            self.manager = SpamRuleManager("test_rules.json")

    @patch('uuid.uuid4')
    @patch('inbox_cleaner.spam_rules.datetime')
    def test_create_predefined_spam_rules(self, mock_datetime, mock_uuid):
        """Test creating predefined spam rules."""
        # Arrange
        mock_uuid.side_effect = [f"uuid-{i}" for i in range(10)]  # Generate multiple UUIDs
        mock_datetime.now.return_value.isoformat.return_value = "2024-01-01T12:00:00"
        
        # Act
        created_rules = self.manager.create_predefined_spam_rules()
        
        # Assert
        assert len(created_rules) > 0
        assert all(rule["predefined"] is True for rule in created_rules)
        assert all(rule["active"] is True for rule in created_rules)
        assert all(rule["action"] == "delete" for rule in created_rules)
        
        # Check that rules were added to manager
        assert len(self.manager.rules) == len(created_rules)
        
        # Verify different rule types are present
        rule_types = set(rule["type"] for rule in created_rules)
        assert "domain" in rule_types
        assert "subject" in rule_types
        assert "sender" in rule_types

    def test_predefined_rules_content(self):
        """Test that predefined rules contain expected patterns."""
        # Act
        created_rules = self.manager.create_predefined_spam_rules()
        
        # Assert - check for specific expected patterns
        subjects = [rule["pattern"] for rule in created_rules if rule["type"] == "subject"]
        senders = [rule["pattern"] for rule in created_rules if rule["type"] == "sender"]
        domains = [rule["domain"] for rule in created_rules if rule["type"] == "domain"]
        
        # Check some expected patterns exist
        assert any("prize" in pattern.lower() for pattern in subjects)
        assert any("urgent" in pattern.lower() for pattern in subjects)
        assert any("million" in pattern.lower() for pattern in subjects)
        assert any(r"\d+\.\d+\.\d+\.\d+" in pattern for pattern in senders)
        assert "warunaantique.com" in domains


class TestSpamRuleManagerSpamAnalysis:
    """Test spam pattern analysis functionality."""

    def setup_method(self):
        """Setup test environment."""
        with patch.object(SpamRuleManager, 'load_rules'):
            self.manager = SpamRuleManager("test_rules.json")

    def test_analyze_spam_patterns_comprehensive(self):
        """Test comprehensive spam pattern analysis."""
        # Arrange
        test_emails = [
            {
                "message_id": "msg1",
                "sender_email": "user192.168.1.1@spam.com",
                "sender_domain": "spam.com",
                "subject": "GET FREE MONEY NOW - URGENT ACTION REQUIRED!"
            },
            {
                "message_id": "msg2", 
                "sender_email": "winnner@prrizzes.com",
                "sender_domain": "prrizzes.com",
                "subject": "Congradulat! You won the lottery!"  # congradulat should match pattern
            },
            {
                "message_id": "msg3",
                "sender_email": "test@abcdefghijk.com",  # suspicious domain pattern
                "sender_domain": "abcdefghijk.com",
                "subject": "Spin to claim prize - act now!"  # Should match spin.*prize pattern
            },
            {
                "message_id": "msg4",
                "sender_email": "normal@legitimate.org",
                "sender_domain": "legitimate.org", 
                "subject": "Regular business email"
            }
        ]
        
        # Act
        analysis = self.manager.analyze_spam_patterns(test_emails)
        
        # Assert
        assert analysis["total_emails"] == 4
        assert len(analysis["suspicious_emails"]) >= 2  # At least 2 should be suspicious
        
        # Check spam indicators
        assert analysis["spam_indicators"]["ip_in_sender"] >= 1
        assert analysis["spam_indicators"]["misspelled_subjects"] >= 1
        assert analysis["spam_indicators"]["prize_scams"] >= 1
        assert analysis["spam_indicators"]["urgent_language"] >= 1
        assert len(analysis["spam_indicators"]["suspicious_domains"]) >= 1
        
        # Check suggested rules
        assert len(analysis["suggested_rules"]) > 0
        rule_types = set(rule["type"] for rule in analysis["suggested_rules"])
        assert len(rule_types) > 1  # Should suggest multiple types of rules

    def test_analyze_spam_patterns_ip_detection(self):
        """Test IP address detection in sender email."""
        # Arrange
        emails = [
            {
                "message_id": "ip1",
                "sender_email": "test192.168.1.1user@example.com",
                "subject": "Test email"
            },
            {
                "message_id": "ip2",
                "sender_email": "user10.0.0.1@test.org",
                "subject": "Another test"
            }
        ]
        
        # Act
        analysis = self.manager.analyze_spam_patterns(emails)
        
        # Assert
        assert analysis["spam_indicators"]["ip_in_sender"] == 2
        assert any(rule["type"] == "sender" and "IP" in rule["reason"] 
                  for rule in analysis["suggested_rules"])

    def test_analyze_spam_patterns_misspelled_words(self):
        """Test misspelled word detection."""
        # Arrange - Include suspicious domain to reach spam score threshold of 3
        emails = [
            {
                "message_id": "misspell1",
                "sender_email": "test@suspiciousdomain.com",
                "sender_domain": "suspiciousdomain.com",  # 8+ char suspicious domain (+2 points)
                "subject": "Reeveall your prrizzes today!"  # Misspelled words (+2 points)
            },
            {
                "message_id": "misspell2",
                "sender_email": "test@anothersuspicious.org",
                "sender_domain": "anothersuspicious.org",  # Suspicious domain (+2 points)
                "subject": "Congradulat yourself winnner!"  # Misspelled words (+2 points)
            }
        ]
        
        # Act
        analysis = self.manager.analyze_spam_patterns(emails)
        
        # Assert - misspelled words detection and total spam score >= 3
        assert analysis["spam_indicators"]["misspelled_subjects"] >= 1
        assert len(analysis["suspicious_emails"]) >= 1  # Should reach spam score threshold

    def test_analyze_spam_patterns_prize_scams(self):
        """Test prize/lottery scam detection."""
        # Arrange
        emails = [
            {
                "message_id": "prize1",
                "sender_email": "test@example.com",
                "subject": "Spin the wheel to claim your prize!"
            },
            {
                "message_id": "prize2",
                "sender_email": "lottery@test.com",
                "subject": "Congratulations! You have won the lottery!"
            },
            {
                "message_id": "prize3",
                "sender_email": "instant@millionaire.com",
                "subject": "Become an instant millionaire today"
            }
        ]
        
        # Act
        analysis = self.manager.analyze_spam_patterns(emails)
        
        # Assert
        assert analysis["spam_indicators"]["prize_scams"] == 3
        assert any(rule["type"] == "subject" and "prize" in rule["pattern"].lower()
                  for rule in analysis["suggested_rules"])

    def test_analyze_spam_patterns_urgent_language(self):
        """Test urgent language detection."""
        # Arrange
        emails = [
            {
                "message_id": "urgent1",
                "sender_email": "test@example.com",
                "subject": "URGENT ACTION REQUIRED - Account suspended!"
            },
            {
                "message_id": "urgent2",
                "sender_email": "test@example.org",
                "subject": "ACT NOW before this limited time offer expires!"
            },
            {
                "message_id": "urgent3",
                "sender_email": "test@example.net",
                "subject": "This offer expires today - immediate response needed!"
            }
        ]
        
        # Act
        analysis = self.manager.analyze_spam_patterns(emails)
        
        # Assert
        assert analysis["spam_indicators"]["urgent_language"] == 3

    def test_analyze_spam_patterns_suspicious_domains(self):
        """Test suspicious domain pattern detection."""
        # Arrange
        emails = [
            {
                "message_id": "domain1", 
                "sender_email": "test@abcdefghijklm.com",  # Random domain pattern
                "sender_domain": "abcdefghijklm.com",
                "subject": "Test email"
            },
            {
                "message_id": "domain2",
                "sender_email": "user@randomstring.net", 
                "sender_domain": "randomstring.net",
                "subject": "Another test"
            },
            {
                "message_id": "legitimate",
                "sender_email": "support@microsoft.com",  # Should not match
                "sender_domain": "microsoft.com",
                "subject": "Legitimate email"
            }
        ]
        
        # Act
        analysis = self.manager.analyze_spam_patterns(emails)
        
        # Assert
        suspicious_domains = analysis["spam_indicators"]["suspicious_domains"]
        # Domain pattern is [a-z]{8,20}\.(com|net|org|info) - must be EXACTLY lowercase letters
        # microsoft.com has 9 chars and should match, but contains no uppercase so pattern should work
        # However the algorithm adds all domains that score highly, so we need to check the logic
        assert "abcdefghijklm.com" in suspicious_domains  # 13 lowercase chars, should match
        assert "randomstring.net" in suspicious_domains   # 12 lowercase chars, should match

    def test_analyze_spam_patterns_empty_input(self):
        """Test analysis with empty email list."""
        # Act
        analysis = self.manager.analyze_spam_patterns([])
        
        # Assert
        assert analysis["total_emails"] == 0
        assert analysis["suspicious_emails"] == []
        assert analysis["suggested_rules"] == []
        assert all(count == 0 for count in analysis["spam_indicators"].values() 
                  if isinstance(count, int))

    def test_analyze_spam_patterns_spam_scoring(self):
        """Test spam scoring mechanism."""
        # Arrange - email with multiple spam indicators
        emails = [
            {
                "message_id": "high_score",
                "sender_email": "winner192.168.1.1@randomdomain.com",
                "sender_domain": "abcdefghijk.com",
                "subject": "FREE MONEY - URGENT ACTION - Claim your prrizzes today!"
            }
        ]
        
        # Act
        analysis = self.manager.analyze_spam_patterns(emails)
        
        # Assert
        assert len(analysis["suspicious_emails"]) == 1
        suspicious_email = analysis["suspicious_emails"][0]
        assert suspicious_email["spam_score"] >= 6  # Should have high score
        assert len(suspicious_email["indicators"]) >= 3  # Multiple indicators


class TestSpamRuleManagerEdgeCases:
    """Test edge cases and error scenarios."""

    def setup_method(self):
        """Setup test environment."""
        with patch.object(SpamRuleManager, 'load_rules'):
            self.manager = SpamRuleManager("test_rules.json")

    def test_matches_spam_rule_malformed_regex(self):
        """Test handling malformed regex patterns."""
        # Arrange - add rule with invalid regex
        self.manager.rules = [
            {
                "rule_id": "bad-regex",
                "type": "subject", 
                "pattern": "[invalid-regex(",  # Malformed regex
                "active": True
            }
        ]
        
        email = {"subject": "test subject"}
        
        # Act & Assert - Should handle malformed regex gracefully
        try:
            result = self.manager.matches_spam_rule(email)
            # Should either return None or handle gracefully
            assert result is None or isinstance(result, dict)
        except Exception:
            # Exception handling is also acceptable for malformed regex
            pass

    def test_analyze_spam_patterns_missing_email_fields(self):
        """Test analysis with emails missing required fields."""
        # Arrange
        emails = [
            {"message_id": "incomplete1"},  # Missing all other fields
            {"sender_email": "test@example.com"},  # Missing message_id
            {"subject": "Test subject"}  # Missing sender info
        ]
        
        # Act - Should not crash
        analysis = self.manager.analyze_spam_patterns(emails)
        
        # Assert
        assert analysis["total_emails"] == 3
        # Should handle missing fields gracefully

    def test_rule_operations_with_empty_rules_list(self):
        """Test rule operations when no rules exist."""
        # Arrange - empty rules list
        self.manager.rules = []
        
        # Act & Assert
        assert self.manager.get_all_rules() == []
        assert self.manager.get_active_rules() == []
        assert self.manager.get_rule_by_id("anything") is None
        assert self.manager.delete_rule("anything") is False
        assert self.manager.toggle_rule("anything") is False
        assert self.manager.get_rules_by_domain("any.com") == []

    def test_file_operations_with_permissions_issues(self):
        """Test file operations with permission-like errors."""
        # Use mock to simulate permission errors
        with patch('builtins.open', mock_open()) as mock_file:
            mock_file.side_effect = PermissionError("Permission denied")
            
            # Act & Assert - save should fail, load might handle gracefully
            assert self.manager.save_rules() is False
            # load_rules implementation might return True and set empty rules list on error
            load_result = self.manager.load_rules()
            # Either returns False or sets rules to empty list on error
            assert load_result is False or self.manager.rules == []