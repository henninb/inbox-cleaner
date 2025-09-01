# Gmail Inbox Cleanup Workflow

## 🎯 Complete Email Analysis & Cleanup Process

This guide walks you through analyzing your 4,225+ emails to identify spam, suspicious content, and unnecessary subscriptions using AI assistance.

## Step 1: Extract Your Emails

Start by extracting your emails in manageable batches:

```bash
# Start with 500 emails to test
python real_demo.py --extract 500

# Then scale up (Gmail API limits ~100-250 requests/minute)
python real_demo.py --extract 1000
python real_demo.py --extract 2000

# Eventually extract all your emails
python real_demo.py --extract 4225
```

**What this does:**
- ✅ Extracts email metadata (sender domains, subjects, labels)
- ✅ Hashes email addresses for privacy (SHA-256)
- ✅ Stores everything locally in SQLite
- ❌ Never stores email content or personal information

## Step 2: Get Your Anthropic API Key

You'll need an Anthropic API key for AI analysis:

1. **Go to**: https://console.anthropic.com/
2. **Sign up** for an account (free tier available)
3. **Create an API key** 
4. **Copy the key** (starts with `sk-ant-...`)

**Cost**: Very minimal - analyzing 4,225 emails costs ~$0.50-1.00

## Step 3: Quick Domain Analysis (Optional)

See your top email domains without AI:

```bash
python analyze_emails.py --domains-only
```

This shows which domains send you the most emails.

## Step 4: Full AI Analysis

Run the complete AI analysis:

```bash
python analyze_emails.py --anthropic-key sk-ant-YOUR_KEY_HERE
```

**What AI analyzes:**
- 🚫 **Spam patterns** - Suspicious domains, social engineering
- 📰 **Newsletter analysis** - Which subscriptions to keep/remove
- ⚠️ **Security risks** - Phishing attempts, suspicious links
- 🏷️ **Category cleanup** - Bulk promotional/social cleanup opportunities
- 🧹 **Bulk actions** - Mass deletion suggestions

## Step 5: Review AI Recommendations

The AI will provide recommendations like:

### 🚫 Spam Domains
```
• suspicious-deals.com (Confidence: 95%)
  Reason: High volume promotional emails with urgency tactics
```

### 📮 Unsubscribe Candidates
```
• daily-newsletter.com (Confidence: 80%)
  Reason: Sends daily emails, low engagement patterns
```

### ⚠️ Security Concerns
```
• fake-security-alert.com [HIGH RISK]
  Potential phishing/social engineering attempts
```

## Step 6: Manual Verification & Action

**Important**: Always manually verify AI recommendations!

### For Spam Domains:
1. **Search Gmail**: `from:suspicious-domain.com`
2. **Review a few emails** to confirm they're spam
3. **Delete if confirmed**: Select all → Delete
4. **Block sender**: Settings → Filters → Block

### For Unsubscribe Candidates:
1. **Review recent emails** from the domain
2. **Use unsubscribe links** (if from legitimate companies)
3. **Or filter to trash** for future emails

### For Security Concerns:
1. **Immediate action**: Search and delete these emails
2. **Report as spam** in Gmail
3. **Check if you clicked any links** (change passwords if needed)

## Step 7: Bulk Cleanup Actions

AI might suggest bulk actions like:

```bash
# Search Gmail for these patterns:
category:promotions older_than:6m    # Old promotional emails
category:social older_than:3m        # Old social media notifications  
from:noreply older_than:1y          # Old automated emails
```

**In Gmail:**
1. **Use the search** above
2. **Select all** (checkbox at top)
3. **Click "Select all conversations that match"**
4. **Delete** or **Archive**

## Step 8: Set Up Prevention

After cleanup, prevent future clutter:

### Gmail Filters:
1. **Settings** → **Filters and Blocked Addresses**
2. **Create filters** for common spam patterns
3. **Auto-delete or label** future similar emails

### Unsubscribe Best Practices:
- ✅ **Legitimate companies**: Use unsubscribe links
- ❌ **Suspicious emails**: Never click unsubscribe (confirms your email is active)
- 🛡️ **Unknown senders**: Block or filter to trash

## 🔒 Privacy & Security Notes

### What's Safe:
- ✅ **Domain names** (e.g., "amazon.com", "github.com") 
- ✅ **Email subjects** (first 50-100 characters)
- ✅ **Gmail labels** (INBOX, PROMOTIONS, etc.)
- ✅ **Aggregated statistics** (email counts, patterns)

### What's Never Shared:
- ❌ **Your email address** (hashed locally)
- ❌ **Email content/body** (never extracted)
- ❌ **Personal information** (names, addresses, etc.)
- ❌ **Sensitive subjects** (truncated to safe lengths)

## 📊 Expected Results

After following this workflow:

- 🗑️ **Delete 20-40% of emails** (spam, old promotions)
- 📮 **Unsubscribe from 10-20 sources** (unnecessary newsletters)
- ⚠️ **Identify 2-5 security risks** (suspicious domains)
- 🛡️ **Set up 5-10 filters** (prevent future clutter)
- ⏰ **Save 10+ minutes daily** (less inbox management)

## 🚨 Red Flags to Watch For

AI will flag these patterns as suspicious:

### Spam Indicators:
- 📈 **High volume** from unknown domains
- 💰 **Money/prize language** in subjects
- ⚡ **Urgency tactics** ("Act now", "Limited time")
- 🎯 **Generic greetings** ("Dear customer")

### Security Risks:
- 🔒 **Fake security alerts** (not from Google/banks you use)
- 🎣 **Phishing attempts** (fake login pages)
- 💸 **Financial scams** (fake invoices, payments)
- 👥 **Social engineering** (impersonation attempts)

## 📞 Getting Help

If you're unsure about recommendations:

```bash
# Get detailed diagnostic info
python diagnose_issues.py

# View domain statistics only
python analyze_emails.py --domains-only

# Save full report for review
python analyze_emails.py --anthropic-key YOUR_KEY --save-report
```

## 🎯 Success Metrics

Track your progress:

```bash
# Before cleanup
python real_demo.py --stats

# After each cleanup phase
python real_demo.py --stats
```

**Goal**: Reduce inbox to manageable size while keeping important emails safe.