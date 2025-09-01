#!/usr/bin/env python3
"""
Manual Gmail cleanup guide - step by step instructions.

Since OAuth is having issues, this shows you exactly how to manually
clean up your 1,490 spam emails using Gmail's web interface.
"""

SPAM_DOMAINS = {
    'trulieve.com': {
        'count': 464,
        'type': 'Cannabis dispensary spam',
        'unsubscribe_links': [
            'https://link.trulieve.com/customer/email_preferences?uid=0130a8f2-8df1-44cf-b932-22d1eb4f8df6&mid=31a462ad-02da-4b92-bf15-d4a55ea4e560&txnid=85918408-d2c5-4601-acf4-0de602eeec97&eid=76b6c796-f0d4-4019-858f-1885684cdfd5&bsft_ek=2025-08-06T20%3A00%3A14Z&bsft_aaid=8b801f73-7e87-4f84-ae74-af279053bf3c&bsft_mime_type=text&bsft_tv=5&bsft_lx=19',
            'mailto:unsubscribe@em3924.trulieve.com'
        ]
    },
    'email.totaltools.com.au': {
        'count': 426,
        'type': 'Australian tool retailer spam',
        'unsubscribe_links': [
            'https://list-unsubscribe.eservice.emarsys.net/api/unsubscribe/818839171_9832250_87586_xLyExCToLn',
            'mailto:list-unsubscribe+818839171_9832250_87586_xLyExCToLn@emarsys.net'
        ]
    },
    't.timberland.com': {
        'count': 338,
        'type': 'Clothing retailer excessive promos',
        'unsubscribe_links': [
            'https://click.t.timberland.com/subscription_center.aspx?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJtaWQiOiI1MTQwMTE4NTUiLCJzIjoiMTUwMTgyNTIzIiwibGlkIjoiMjYiLCJqIjoiMTg4NzI4IiwiamIiOiIyOTgzIiwiZCI6IjExMDA0NSJ9.tt5Wn3WBmHIMYvjGn2GA7azHUKonjRX5jCOvBuqmM_g',
            'mailto:leave-fd8316761a3c402029-fe34157575650c7f701673-febd15787d630675-fe3111717164057c7d1175-ff2916797d67@leave.t.timberland.com'
        ]
    },
    'info.curaleaf.com': {
        'count': 262,
        'type': 'Cannabis company spam',
        'unsubscribe_links': [
            'https://u51914220.ct.sendgrid.net/wf/unsubscribe?upn=u001.dRhFteEzY6YnNfS5QhgFw4XkPm2-2B9B7qibgCoQI1qa42ZslFbBg6jnH5ddTk0-2Bt0XtWiHxpZqgvIWctLccutOTHCn-2FTO2neK5WVkrplbGfwWgLH5-2BWXDbWUTGke-2F-2BXenqKZ0i9QKo2lv-2B7WnnBgPuStwC-2FYfOegAfnw-2FOwJdAqXwA-2Bo8N7FoSkIwE6U-2B1VxlUiJzr97h-2BYqPGvHAG6ZgAUiQUkxoxP5jvEt0BkAVeEpdRw22grR8-2Br49tkvfMPEzDyh-2BSlT-2Boz9CP3AIemAceYpTkuVue5ThJ4vUzdn-2BC7QZb-2BvtgH-2Ft5R1WChkpAuDkBqy-2FCXzuQMiQDI4D1AeUzhU2mQ5JD2ThPdL4OpemAih0JCEW-2FFlTvOsyM1f1GVPfsVPVhLB-2BgMD-2FU0MdS0OKKksZFR2KkwQttb9hQVJCZT-2BkUjUJvytyQBm2VkkUnzak',
            'mailto:unsubscribe@em7233.info.curaleaf.com'
        ]
    }
}

def print_cleanup_guide():
    """Print comprehensive manual cleanup guide."""
    
    print("🎯 MANUAL GMAIL CLEANUP GUIDE")
    print("=" * 60)
    print()
    print("🎊 GREAT NEWS: We found unsubscribe links for all spam domains!")
    print("📊 Impact: Delete 1,490 emails (40% of your inbox)")
    print()
    
    total_emails = sum(domain['count'] for domain in SPAM_DOMAINS.values())
    print(f"📧 Total spam emails to eliminate: {total_emails}")
    print()
    
    print("🚀 STEP-BY-STEP CLEANUP PROCESS:")
    print("=" * 40)
    print()
    
    for i, (domain, info) in enumerate(SPAM_DOMAINS.items(), 1):
        print(f"📌 DOMAIN {i}/4: {domain}")
        print(f"   📊 Emails: {info['count']}")
        print(f"   🏷️  Type: {info['type']}")
        print()
        
        print("   ✋ STEP A: UNSUBSCRIBE FIRST")
        print("   Click these links to unsubscribe:")
        for j, link in enumerate(info['unsubscribe_links'], 1):
            if link.startswith('mailto:'):
                print(f"      {j}. 📧 Send email to: {link.replace('mailto:', '')}")
            else:
                print(f"      {j}. 🔗 {link}")
        print()
        
        print("   🛡️ STEP B: CREATE GMAIL FILTER")
        print("   1. In Gmail, click ⚙️ (gear icon) → 'See all settings'")
        print("   2. Click 'Filters and Blocked Addresses' tab")
        print("   3. Click 'Create a new filter'")
        print(f"   4. In 'From' field, enter: {domain}")
        print("   5. Click 'Create filter'")
        print("   6. Check ☑️ 'Delete it'")
        print("   7. Check ☑️ 'Also apply filter to matching conversations'")
        print("   8. Click 'Create filter'")
        print()
        
        print("   🗑️ STEP C: DELETE EXISTING EMAILS (if filter didn't catch them)")
        print(f"   1. In Gmail search box, type: from:{domain}")
        print("   2. Press Enter")
        print("   3. Click 'Select all' checkbox at top")
        print("   4. Click 'Select all conversations that match this search'")
        print("   5. Click 🗑️ Delete button")
        print()
        
        print("   " + "="*50)
        print()
    
    print("📈 EXPECTED RESULTS AFTER CLEANUP:")
    print("=" * 40)
    print("✅ Unsubscribed from all 4 major spam sources")
    print("✅ Created 4 Gmail filters to auto-delete future spam")
    print(f"✅ Deleted {total_emails} existing spam emails")
    print("✅ Reduced inbox size by 40%")
    print("✅ Future emails from these domains will be auto-deleted")
    print()
    
    print("🕒 TIME ESTIMATE: 15-20 minutes total")
    print("🏆 PAYOFF: Dramatically cleaner inbox forever")
    print()
    
    print("💡 PRO TIPS:")
    print("=" * 20)
    print("• Do the unsubscribe FIRST before creating filters")
    print("• The filters will prevent any future emails")
    print("• Check the 'Also apply to matching conversations' option")
    print("• This will handle both existing and future emails")
    print()
    
    print("🎯 PRIORITY ORDER:")
    print("=" * 20)
    print("1. trulieve.com (464 emails) - Biggest impact")
    print("2. email.totaltools.com.au (426 emails)")
    print("3. t.timberland.com (338 emails)")
    print("4. info.curaleaf.com (262 emails)")
    print()
    
    print("🔍 VERIFICATION:")
    print("=" * 20)
    print("After completing all domains:")
    print("1. Search Gmail for: from:trulieve.com")
    print("2. Should show: 'No conversations found'")
    print("3. Check Settings → Filters to see your 4 new filters")
    print()


if __name__ == '__main__':
    print_cleanup_guide()