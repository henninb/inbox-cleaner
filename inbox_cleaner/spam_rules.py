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

    def create_predefined_spam_rules(self) -> List[Dict[str, Any]]:
        """Create predefined rules for common spam patterns."""
        predefined_rules = [
            # Prize/lottery scams
            {
                "type": "subject",
                "pattern": r"(spin|prize|winner|lottery|millionaire|claim.*prize|congratulations.*won)",
                "action": "delete",
                "reason": "Prize/lottery spam scam"
            },
            
            # Suspicious sender patterns (emails with IPs)
            {
                "type": "sender", 
                "pattern": r".*\d+\.\d+\.\d+\.\d+.*@",
                "action": "delete",
                "reason": "Sender email contains IP address (suspicious)"
            },
            
            # Random character domains (like warunaantique.com pattern)
            {
                "type": "sender",
                "pattern": r"@[a-z]{8,20}\.(com|net|org|info)$",
                "action": "delete", 
                "reason": "Random/suspicious domain name"
            },
            
            # Misspelled common words in subject
            {
                "type": "subject",
                "pattern": r"(reeveall|yourr|prrizzes|claiim|winnner|congradulat)",
                "action": "delete",
                "reason": "Deliberately misspelled spam words"
            },
            
            # Generic suspicious domains
            {
                "type": "domain",
                "domain": "warunaantique.com",
                "action": "delete",
                "reason": "Known spam domain"
            },
            
            # Money/financial scams
            {
                "type": "subject",
                "pattern": r"(million.*dollar|inheritance|beneficiary|fund.*transfer|wire.*transfer)",
                "action": "delete",
                "reason": "Financial scam pattern"
            },
            
            # Urgent action required
            {
                "type": "subject", 
                "pattern": r"(urgent.*action|immediate.*response|time.*limited|expires.*today|act.*now)",
                "action": "delete",
                "reason": "Urgent action spam pattern"
            },
            
            # Suspicious forwarding emails (bcc patterns)
            {
                "type": "sender",
                "pattern": r".*[A-Z]{2,}[a-z]{2,}[A-Z]{2,}.*@outlook\.com",
                "action": "delete", 
                "reason": "Suspicious forwarding email pattern"
            }
        ]
        
        created_rules = []
        for rule_data in predefined_rules:
            rule = {
                "rule_id": str(uuid.uuid4()),
                "type": rule_data["type"],
                "action": rule_data["action"],
                "reason": rule_data["reason"],
                "created_at": datetime.now().isoformat(),
                "active": True,
                "predefined": True
            }
            
            if rule_data["type"] == "domain":
                rule["domain"] = rule_data.get("domain")
            else:
                rule["pattern"] = rule_data.get("pattern")
            
            self.rules.append(rule)
            created_rules.append(rule)
        
        return created_rules

    def analyze_spam_patterns(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze a batch of emails for spam patterns and suggest rules."""
        analysis = {
            "total_emails": len(emails),
            "suspicious_emails": [],
            "suggested_rules": [],
            "spam_indicators": {
                "ip_in_sender": 0,
                "suspicious_domains": [],
                "misspelled_subjects": 0,
                "prize_scams": 0,
                "urgent_language": 0
            }
        }
        
        suspicious_domains = set()
        
        for email in emails:
            sender = email.get("sender_email", "")
            subject = email.get("subject", "")
            domain = email.get("sender_domain", "")
            
            spam_score = 0
            indicators = []
            
            # Check for IP in sender email
            if re.search(r"\d+\.\d+\.\d+\.\d+", sender):
                spam_score += 3
                indicators.append("IP in sender email")
                analysis["spam_indicators"]["ip_in_sender"] += 1
            
            # Check for misspelled common words
            misspell_patterns = [
                r"reeveall", r"yourr", r"prrizzes", r"claiim", 
                r"winnner", r"congradulat", r"recieve", r"seperate"
            ]
            for pattern in misspell_patterns:
                if re.search(pattern, subject, re.IGNORECASE):
                    spam_score += 2
                    indicators.append("Misspelled words")
                    analysis["spam_indicators"]["misspelled_subjects"] += 1
                    break
            
            # Check for prize/lottery scams
            prize_patterns = [
                r"spin.*prize", r"instant.*millionaire", r"claim.*prize",
                r"lottery.*winner", r"congratulations.*won"
            ]
            for pattern in prize_patterns:
                if re.search(pattern, subject, re.IGNORECASE):
                    spam_score += 4
                    indicators.append("Prize/lottery scam")
                    analysis["spam_indicators"]["prize_scams"] += 1
                    break
            
            # Check for urgent language
            urgent_patterns = [
                r"urgent.*action", r"act.*now", r"limited.*time",
                r"expires.*today", r"immediate.*response"
            ]
            for pattern in urgent_patterns:
                if re.search(pattern, subject, re.IGNORECASE):
                    spam_score += 2
                    indicators.append("Urgent language")
                    analysis["spam_indicators"]["urgent_language"] += 1
                    break
            
            # Check for suspicious domain patterns
            if re.match(r"^[a-z]{8,20}\.(com|net|org|info)$", domain):
                spam_score += 2
                indicators.append("Suspicious domain pattern")
                suspicious_domains.add(domain)
            
            # If spam score is high enough, mark as suspicious
            if spam_score >= 3:
                analysis["suspicious_emails"].append({
                    "message_id": email.get("message_id"),
                    "sender": sender,
                    "subject": subject,
                    "spam_score": spam_score,
                    "indicators": indicators
                })
        
        analysis["spam_indicators"]["suspicious_domains"] = list(suspicious_domains)
        
        # Generate suggested rules based on analysis
        if analysis["spam_indicators"]["ip_in_sender"] > 0:
            analysis["suggested_rules"].append({
                "type": "sender",
                "pattern": r".*\d+\.\d+\.\d+\.\d+.*@",
                "reason": f"Found {analysis['spam_indicators']['ip_in_sender']} emails with IP addresses in sender"
            })
        
        if analysis["spam_indicators"]["prize_scams"] > 0:
            analysis["suggested_rules"].append({
                "type": "subject", 
                "pattern": r"(spin|prize|winner|lottery|millionaire|claim.*prize)",
                "reason": f"Found {analysis['spam_indicators']['prize_scams']} prize/lottery scam emails"
            })
        
        for domain in suspicious_domains:
            analysis["suggested_rules"].append({
                "type": "domain",
                "domain": domain,
                "reason": f"Suspicious domain pattern detected"
            })
        
        return analysis