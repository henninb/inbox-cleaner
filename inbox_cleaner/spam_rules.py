"""Spam rule management system for automated email filtering."""

import json
import re
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path


class SpamRuleManager:
    """Manages spam filtering rules for automatic email actions."""

    def __init__(self, rules_file: str = "spam_rules.json"):
        """Initialize spam rule manager."""
        self.rules_file = rules_file
        self.rules: List[Dict[str, Any]] = []
        self.load_rules()

    def create_domain_rule(self, domain: str, action: str, reason: str) -> Dict[str, Any]:
        """Create a rule that matches emails from a specific domain."""
        rule = {
            "rule_id": str(uuid.uuid4()),
            "type": "domain",
            "domain": domain,
            "action": action,
            "reason": reason,
            "created_at": datetime.now().isoformat(),
            "active": True
        }
        
        self.rules.append(rule)
        return rule

    def create_subject_rule(self, pattern: str, action: str, reason: str) -> Dict[str, Any]:
        """Create a rule that matches emails by subject pattern (regex)."""
        rule = {
            "rule_id": str(uuid.uuid4()),
            "type": "subject",
            "pattern": pattern,
            "action": action,
            "reason": reason,
            "created_at": datetime.now().isoformat(),
            "active": True
        }
        
        self.rules.append(rule)
        return rule

    def create_sender_rule(self, sender_pattern: str, action: str, reason: str) -> Dict[str, Any]:
        """Create a rule that matches emails by sender pattern (regex)."""
        rule = {
            "rule_id": str(uuid.uuid4()),
            "type": "sender",
            "pattern": sender_pattern,
            "action": action,
            "reason": reason,
            "created_at": datetime.now().isoformat(),
            "active": True
        }
        
        self.rules.append(rule)
        return rule

    def matches_spam_rule(self, email: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if an email matches any spam rule."""
        for rule in self.rules:
            if not rule.get("active", True):
                continue
                
            if rule["type"] == "domain":
                if email.get("sender_domain") == rule["domain"]:
                    return rule
                    
            elif rule["type"] == "subject":
                subject = email.get("subject", "")
                if re.search(rule["pattern"], subject, re.IGNORECASE):
                    return rule
                    
            elif rule["type"] == "sender":
                sender = email.get("sender_email", "")
                if re.search(rule["pattern"], sender, re.IGNORECASE):
                    return rule
        
        return None

    def get_all_rules(self) -> List[Dict[str, Any]]:
        """Get all spam rules."""
        return self.rules.copy()

    def get_active_rules(self) -> List[Dict[str, Any]]:
        """Get only active spam rules."""
        return [rule for rule in self.rules if rule.get("active", True)]

    def get_rule_by_id(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific rule by ID."""
        for rule in self.rules:
            if rule["rule_id"] == rule_id:
                return rule
        return None

    def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing rule."""
        rule = self.get_rule_by_id(rule_id)
        if rule:
            rule.update(updates)
            rule["updated_at"] = datetime.now().isoformat()
            return True
        return False

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule by ID."""
        for i, rule in enumerate(self.rules):
            if rule["rule_id"] == rule_id:
                del self.rules[i]
                return True
        return False

    def toggle_rule(self, rule_id: str) -> bool:
        """Toggle a rule active/inactive."""
        rule = self.get_rule_by_id(rule_id)
        if rule:
            rule["active"] = not rule.get("active", True)
            rule["updated_at"] = datetime.now().isoformat()
            return True
        return False

    def save_rules(self) -> bool:
        """Save rules to file."""
        try:
            with open(self.rules_file, 'w') as f:
                json.dump(self.rules, f, indent=2)
            return True
        except Exception:
            return False

    def load_rules(self) -> bool:
        """Load rules from file."""
        try:
            if Path(self.rules_file).exists():
                with open(self.rules_file, 'r') as f:
                    self.rules = json.load(f)
            else:
                self.rules = []
            return True
        except Exception:
            self.rules = []
            return False

    def get_rules_by_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get all rules that target a specific domain."""
        return [
            rule for rule in self.rules 
            if rule.get("type") == "domain" and rule.get("domain") == domain
        ]

    def get_deletion_stats(self) -> Dict[str, Any]:
        """Get statistics about rules and their actions."""
        stats = {
            "total_rules": len(self.rules),
            "active_rules": len(self.get_active_rules()),
            "deletion_rules": len([r for r in self.rules if r.get("action") == "delete"]),
            "rules_by_type": {}
        }
        
        # Count by type
        for rule in self.rules:
            rule_type = rule.get("type", "unknown")
            if rule_type not in stats["rules_by_type"]:
                stats["rules_by_type"][rule_type] = 0
            stats["rules_by_type"][rule_type] += 1
        
        return stats