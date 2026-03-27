# Incident Response Decision: Active RCE Exploit in Customer-Facing Service

## Situation

A remote code execution vulnerability (CVE-2026-1847) has been confirmed in our customer-facing authentication service. The vulnerability exists in the session deserialization module and allows unauthenticated attackers to execute arbitrary commands on the application servers.

Active exploitation has been confirmed: our SIEM detected 12 successful exploitation attempts in the last 6 hours. The attacker has achieved command execution on 3 of 8 application pods but has not yet moved laterally to the database tier.

## Current state

- Service handles 45,000 active sessions across 180 enterprise customers
- It is 2:00 PM on a Thursday — peak business hours
- The vendor patch (v3.1.2) is available but has not been tested against our custom SAML integration
- A WAF rule can block the known exploit pattern but has a 15% false-positive rate on legitimate SAML assertions
- Full service shutdown would terminate all active sessions and require customers to re-authenticate

## Options to evaluate

**Option 1: Emergency patch deployment**
Apply vendor patch v3.1.2 immediately without full regression testing. Risk: SAML integration may break, locking out legitimate users. Benefit: eliminates the root cause.

**Option 2: WAF mitigation + scheduled patch**
Deploy the WAF rule now to block known exploit signatures. Schedule the patch for the next maintenance window (Saturday 02:00). Risk: 15% false positive rate disrupts some users; new exploit variants may bypass the WAF. Benefit: buys time for testing.

**Option 3: Controlled service isolation**
Take the 3 compromised pods offline immediately. Redirect traffic to the 5 clean pods. Deploy WAF rule on clean pods. Patch the isolated pods, test, then rotate back in. Risk: 37.5% capacity reduction during peak hours. Benefit: contains the breach while preserving partial service.

**Option 4: Full service shutdown**
Shut down the authentication service entirely. Notify all 180 customers of emergency maintenance. Patch, test, and redeploy. Risk: complete service outage for 2-4 hours during business hours. Benefit: eliminates all attack surface immediately.

## What we need

Determine the right course of action. This is both a factual question (what is the actual risk of each option) and a recommendation question (which option should we choose given our constraints). We need consensus on the facts AND a clear recommendation.
