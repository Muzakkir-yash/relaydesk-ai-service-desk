"""
Comprehensive ticket seeding script for NexusIT / RelayDesk.
Generates 55+ distinct, realistic, perfectly matched tickets across:
- Realistic Hostnames & Devices (Dell, MacBook, ThinkPad, Surface, Linux WS)
- Accurate Categories & Priorities
- Full realistic Message Threads (User question -> AI Diagnostic with exact KB -> Technician handover & resolution)
- Comprehensive Handover Briefings for escalated/in-progress tickets
- Rich Date Distribution (This Week, This Year, Last Year 2025, Older >1 Year)
"""

import sys
import os
from datetime import datetime, timedelta
import random

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, engine, Base
import models
from auth import hash_password

db = SessionLocal()

print("🧹 Clearing previous tickets, messages, briefings, and ratings...")
db.query(models.TicketRating).delete()
db.query(models.HandoverBriefing).delete()
db.query(models.TicketMessage).delete()
db.query(models.AIAction).delete()
db.query(models.Ticket).delete()
db.commit()

# Ensure users exist
users = {u.email: u for u in db.query(models.User).all()}
alice = users.get("alice@company.com")
bob = users.get("bob@company.com")
charlie = users.get("charlie@company.com")
diana = users.get("diana@company.com")
marcus = users.get("marcus@company.com")
admin = users.get("admin@company.com")

if not alice or not bob or not charlie:
    print("❌ Users missing, run standard seed first.")
    sys.exit(1)

# Device catalog templates
devices = [
    {
        "device_name": "CORP-LAPTOP-W11-842",
        "device_os": "Windows 11 Enterprise (23H2)",
        "ip_address": "10.14.88.24",
        "subnet_vlan": "VLAN 20 (HQ Floor 3 - Engineering)",
        "mac_address": "00:1A:2B:3C:4D:5E",
        "asset_tag": "AST-84291",
        "serial_number": "PF39X8K2",
        "last_reboot": "3 days ago (Uptime: 74h 12m)",
        "edr_status": "CrowdStrike Falcon (Healthy / v7.14.0)",
        "hardware_specs": "Intel Core i7-1370P | 32 GB RAM | 512 GB NVMe (184 GB Free)",
        "domain_join": "CORP.INTERNAL (Azure AD Hybrid / Intune Compliant)",
        "office_location": "HQ - Building B - Desk 304",
    },
    {
        "device_name": "CORP-MBP-M3-104",
        "device_os": "macOS Sonoma 14.5 (Build 23F79)",
        "ip_address": "10.14.92.55",
        "subnet_vlan": "VLAN 30 (HQ Floor 2 - Design & Marketing)",
        "mac_address": "A4:83:E7:2B:11:90",
        "asset_tag": "AST-91024",
        "serial_number": "C02GL412MD6R",
        "last_reboot": "12 hours ago (Uptime: 12h 4m)",
        "edr_status": "CrowdStrike Falcon (Healthy / v7.14.0)",
        "hardware_specs": "Apple M3 Pro | 36 GB Unified Memory | 1 TB SSD (620 GB Free)",
        "domain_join": "CORP.INTERNAL (Jamf Pro Managed / Compliant)",
        "office_location": "HQ - Building A - Studio 12",
    },
    {
        "device_name": "ENG-DELL-5530-91",
        "device_os": "Windows 11 Enterprise (23H2)",
        "ip_address": "10.14.88.112",
        "subnet_vlan": "VLAN 20 (HQ Floor 3 - Engineering)",
        "mac_address": "3C:52:82:44:91:1A",
        "asset_tag": "AST-55302",
        "serial_number": "DL99X21B",
        "last_reboot": "1 day ago (Uptime: 26h 10m)",
        "edr_status": "CrowdStrike Falcon (Healthy / v7.14.0)",
        "hardware_specs": "Intel Core i9-13900H | 64 GB RAM | 1 TB NVMe (410 GB Free)",
        "domain_join": "CORP.INTERNAL (Azure AD Hybrid / Intune Compliant)",
        "office_location": "HQ - Building B - Desk 318",
    },
    {
        "device_name": "FIN-DESKTOP-302",
        "device_os": "Windows 11 Pro (22H2)",
        "ip_address": "10.14.70.12",
        "subnet_vlan": "VLAN 10 (HQ Floor 1 - Finance)",
        "mac_address": "70:85:C2:10:4A:88",
        "asset_tag": "AST-30214",
        "serial_number": "HP88319Z",
        "last_reboot": "5 days ago (Uptime: 120h 33m)",
        "edr_status": "CrowdStrike Falcon (Healthy / v7.14.0)",
        "hardware_specs": "Intel Core i5-12500 | 16 GB RAM | 256 GB SSD (95 GB Free)",
        "domain_join": "CORP.INTERNAL (Active Directory Domain Joined)",
        "office_location": "HQ - Building A - Desk 102",
    },
    {
        "device_name": "SALES-THINKPAD-X1",
        "device_os": "Windows 11 Enterprise (23H2)",
        "ip_address": "10.20.14.77",
        "subnet_vlan": "VLAN 40 (HQ Floor 4 - Sales & Ops)",
        "mac_address": "48:2A:E3:77:88:99",
        "asset_tag": "AST-77102",
        "serial_number": "TPX1-8841",
        "last_reboot": "2 days ago (Uptime: 48h 15m)",
        "edr_status": "CrowdStrike Falcon (Healthy / v7.14.0)",
        "hardware_specs": "Intel Core i7-1365U | 16 GB RAM | 512 GB SSD (280 GB Free)",
        "domain_join": "CORP.INTERNAL (Intune Enrolled)",
        "office_location": "HQ - Building C - Desk 409",
    },
    {
        "device_name": "DEV-UBUNTU-WS04",
        "device_os": "Ubuntu Linux 22.04 LTS",
        "ip_address": "10.14.89.44",
        "subnet_vlan": "VLAN 25 (Dev Lab Subnet)",
        "mac_address": "00:1B:44:11:3A:9F",
        "asset_tag": "AST-66014",
        "serial_number": "LX-99014",
        "last_reboot": "14 days ago (Uptime: 336h)",
        "edr_status": "CrowdStrike Falcon Linux (v7.12.1)",
        "hardware_specs": "AMD Ryzen 9 7950X | 64 GB DDR5 | 2 TB NVMe (1.4 TB Free)",
        "domain_join": "CORP.INTERNAL (SSSD Kerberos Realm)",
        "office_location": "HQ - Building B - Lab 4",
    },
]

raw_tickets = [
    # ── Category 1: Network & VPN ──────────────────────────────────────────
    {
        "subject": "Cannot connect to Cisco AnyConnect VPN client",
        "description": "I've been trying to connect to the corporate VPN from home since this morning, but the client keeps timing out at 'Contacting secure gateway'. I need access for an urgent presentation.",
        "category": "network", "priority": "high", "status": "deflected",
        "user_email": "alice@company.com", "days_ago": 1,
        "ai_kb": "VPN Connection Issues — Troubleshooting Guide",
        "ai_solution": "1. Disconnect and reconnect in AnyConnect.\n2. In VPN Preferences, switch protocol from UDP to TCP.\n3. Open Command Prompt as Administrator and run 'ipconfig /flushdns'.\n4. Restart the Cisco AnyConnect Secure Mobility Agent in Windows Services.",
        "user_followup": "Flushing DNS and switching to TCP resolved the timeout immediately. Thank you!",
    },
    {
        "subject": "HQ 3rd floor Wi-Fi keeps disconnecting intermittently",
        "description": "While working at desk 304 on Floor 3, my Wi-Fi drops every 15 to 20 minutes and shows 'No Internet, Secured'. Other colleagues near desk 310 report similar drops.",
        "category": "network", "priority": "medium", "status": "in_progress",
        "user_email": "alice@company.com", "assigned_email": "charlie@company.com", "days_ago": 2,
        "ai_kb": "Wi-Fi & Wireless Network Connection Troubleshooting",
        "ai_solution": "1. Forget network 'Company-Corp-Secure' and reconnect.\n2. In Device Manager, disable Wi-Fi power saving ('Allow the computer to turn off this device to save power').\n3. Run 'netsh wlan show interfaces' to inspect signal RSSI.",
        "tech_reply": "Investigated AP-HQ3-NORTH controller logs. Discovered channel 36 congestion and 5GHz radio band flapping. Rebalancing wireless channels across floor 3 now.",
    },
    {
        "subject": "SSL Certificate error SEC_ERROR_EXPIRED_CERTIFICATE on staging API",
        "description": "When accessing https://staging-api.corp.internal/v2 from Chrome and curl, I receive an expired SSL certificate warning. It is blocking end-to-end integration tests.",
        "category": "network", "priority": "high", "status": "resolved",
        "user_email": "bob@company.com", "assigned_email": "marcus@company.com", "days_ago": 5,
        "ai_kb": "Wi-Fi & Wireless Network Connection Troubleshooting",
        "ai_solution": "Internal wildcard certificate *.corp.internal expired at 00:00 UTC. Escalating to Infrastructure Team for cert-manager renewal.",
        "tech_reply": "Renewed wildcard certificate on Let's Encrypt / Vault PKI backend. Reloaded NGINX reverse proxy pods. Verified valid through next year.",
    },
    {
        "subject": "Shared network drive Z: inaccessible over VPN (System Error 53)",
        "description": "Attempting to open the mapped network drive Z: (\\\\fileserver.company.internal\\finance) fails with 'The network path was not found'. My VPN is active.",
        "category": "network", "priority": "medium", "status": "deflected",
        "user_email": "alice@company.com", "days_ago": 6,
        "ai_kb": "Shared Network Drives, OneDrive & SharePoint Access Issues",
        "ai_solution": "1. Verify DNS resolution: Run 'nslookup fileserver.company.internal' in Command Prompt.\n2. Open File Explorer → address bar → type '\\\\10.14.10.50\\finance' directly.\n3. Disconnect drive Z: and remap using the fully qualified domain name.",
        "user_followup": "Typing the FQDN path reconnected the drive properly. Thanks for the quick solution!",
    },
    {
        "subject": "Ethernet wall jack B-304 has no link light or DHCP IP",
        "description": "Plugged my laptop docking station into wall jack B-304 in Building B. The RJ45 port LED is completely dark and Windows reports 'Network cable unplugged'.",
        "category": "network", "priority": "low", "status": "resolved",
        "user_email": "bob@company.com", "assigned_email": "charlie@company.com", "days_ago": 12,
        "tech_reply": "Checked patch panel 3B in IDF closet. Port B-304 was unpatched during the recent floor rearrangement. Patched to Switch-02 Port 24 (VLAN 20). Verified 1Gbps link.",
    },
    {
        "subject": "GlobalProtect VPN returns Error 519: Radius authentication failed",
        "description": "Unable to log in via GlobalProtect. After submitting MFA push, client displays 'Authentication Failed: Error 519'.",
        "category": "network", "priority": "high", "status": "resolved",
        "user_email": "alice@company.com", "assigned_email": "charlie@company.com", "days_ago": 18,
        "tech_reply": "Found duplicate stale NPS server session token in Active Directory Radius server. Purged session cache and re-authenticated user account.",
    },

    # ── Category 2: Hardware ──────────────────────────────────────────────
    {
        "subject": "Dell Latitude laptop won't turn on (3 amber blinks)",
        "description": "My Dell laptop won't power on at all. When I press the power button, the LED blinks amber 3 times, pauses, then stays off. This happened after leaving it on the charger overnight.",
        "category": "hardware", "priority": "critical", "status": "in_progress",
        "user_email": "alice@company.com", "assigned_email": "diana@company.com", "days_ago": 1,
        "ai_kb": "Laptop Won't Turn On — Hardware Troubleshooting",
        "ai_solution": "1. Disconnect charger and all peripherals.\n2. Hold the power button down for 30 full seconds to drain static charge.\n3. Connect the OEM charger directly to wall outlet and try powering on.\nNote: 3 amber blinks on Dell Latitude indicates CMOS / motherboard power rail protection.",
        "tech_reply": "Diana: Diagnostic 3-blink code confirms motherboard regulator trigger. I have prepared a replacement Dell Latitude 5540 loaner unit ready for pickup at Desk L1.",
    },
    {
        "subject": "Dual 4K external monitor docking station not detecting DisplayPort",
        "description": "Connected the Dell Thunderbolt dock via USB-C to my workstation. Monitor 1 works fine, but Monitor 2 displays 'No Signal' on DisplayPort 2.",
        "category": "hardware", "priority": "medium", "status": "deflected",
        "user_email": "bob@company.com", "days_ago": 3,
        "ai_kb": "External Monitor & Dual Display Configuration Issues",
        "ai_solution": "1. Power cycle the docking station: Unplug dock AC power for 20 seconds.\n2. Press Win + Ctrl + Shift + B to restart the graphics subsystem.\n3. In Windows Settings → System → Display → Multiple Displays → click 'Detect'.",
        "user_followup": "Power cycling the dock and pressing Win+Ctrl+Shift+B brought back the second screen instantly!",
    },
    {
        "subject": "Laptop battery swelling causing trackpad to physically click stiffly",
        "description": "The lower chassis of my MacBook Pro is slightly bulging and the trackpad is very difficult to click down physically. I am concerned about battery safety.",
        "category": "hardware", "priority": "critical", "status": "resolved",
        "user_email": "bob@company.com", "assigned_email": "diana@company.com", "days_ago": 9,
        "tech_reply": "Safety critical: Immediately powered off device and safely quarantined battery. Provided user with replacement M3 Max workstation AST-91088.",
    },
    {
        "subject": "HP LaserJet Enterprise printer paper jam in Tray 2",
        "description": "The shared HP LaserJet printer on floor 2 in the accounting hallway reports '13.00.00 Jam in Tray 2' and will not process any print jobs.",
        "category": "hardware", "priority": "high", "status": "resolved",
        "user_email": "alice@company.com", "assigned_email": "diana@company.com", "days_ago": 14,
        "ai_kb": "Network Printer Not Found or Printer Offline",
        "tech_reply": "Cleared accordion paper jam stuck behind the duplexer pickup rollers. Cleaned rubber pickup assembly with isopropyl alcohol. Test page printed cleanly.",
    },
    {
        "subject": "Thermal throttling and excessive fan noise at idle",
        "description": "My laptop fans are running at 100% maximum speed constantly even with no applications open. Task Manager shows CPU temperature reaching 98°C and clock speed throttled to 0.79 GHz.",
        "category": "hardware", "priority": "medium", "status": "resolved",
        "user_email": "bob@company.com", "assigned_email": "diana@company.com", "days_ago": 22,
        "tech_reply": "Disassembled laptop cooling block. Removed heavy dust buildup in exhaust fins and reapplied Arctic MX-4 thermal compound. Idle temps dropped to 42°C.",
    },
    {
        "subject": "Mechanical keyboard repeating keystrokes (chattering)",
        "description": "My company-issued mechanical keyboard frequently types double 'ee' and 'tt' letters when typing emails.",
        "category": "hardware", "priority": "low", "status": "resolved",
        "user_email": "alice@company.com", "assigned_email": "diana@company.com", "days_ago": 35,
        "tech_reply": "Replaced faulty Cherry MX brown switch on E and T key sockets. Cleaned PCB with contact cleaner. Tested with typing benchmark - 0 duplicate keys.",
    },

    # ── Category 3: Software & Applications ────────────────────────────────
    {
        "subject": "Microsoft Teams microphone not recognized in meetings",
        "description": "When joining Microsoft Teams calls, other participants cannot hear me. The microphone icon shows unmuted, but Teams audio settings shows 'Custom Audio Device: Not Detected'.",
        "category": "software", "priority": "medium", "status": "deflected",
        "user_email": "alice@company.com", "days_ago": 2,
        "ai_kb": "Microsoft Teams & Zoom Audio / Video / Microphone Troubleshooting",
        "ai_solution": "1. In Teams: Settings → Devices → change Audio devices from 'Custom' to 'Headset (Jabra Evolve2)'.\n2. Windows Settings → Privacy & security → Microphone → Ensure 'Let desktop apps access microphone' is ON.\n3. Quit Teams completely from system tray and restart.",
        "user_followup": "Selecting the Jabra headset directly in Teams device settings fixed the audio! Thank you.",
    },
    {
        "subject": "Outlook constantly prompting for Office 365 credentials",
        "description": "Every few minutes, a dialog pop-up appears in Outlook saying 'Enter your password' or 'Need Password' in the bottom right corner, but submitting password causes it to pop up again.",
        "category": "software", "priority": "high", "status": "deflected",
        "user_email": "bob@company.com", "days_ago": 4,
        "ai_kb": "Microsoft Outlook & Corporate Email Sync / Password Prompt Issues",
        "ai_solution": "1. Open Windows Control Panel → Credential Manager → Windows Credentials.\n2. Under Generic Credentials, remove all entries starting with 'MicrosoftOffice16' or 'MS.Outlook'.\n3. Restart Outlook. It will trigger modern OAuth2 browser authentication.",
        "user_followup": "Removing the stale credentials from Credential Manager stopped the password loop. All syncing now.",
    },
    {
        "subject": "Blue Screen (BSOD) SYSTEM_SERVICE_EXCEPTION after Windows Update",
        "description": "My computer crashed with a blue screen error 'SYSTEM_SERVICE_EXCEPTION (csagent.sys)' right after installing the cumulative Windows update last night.",
        "category": "software", "priority": "critical", "status": "resolved",
        "user_email": "alice@company.com", "assigned_email": "marcus@company.com", "days_ago": 8,
        "ai_kb": "Blue Screen of Death (BSOD) & Windows System Crashes",
        "tech_reply": "Analyzed minidump at C:\\Windows\\Minidump. Identified conflicting CrowdStrike Falcon sensor channel file. Pushed sensor update v7.14.1 and executed DISM /Online /Cleanup-image /Restorehealth. System stable.",
    },
    {
        "subject": "Docker Desktop fails to start WSL2 Linux backend engine",
        "description": "Starting Docker Desktop gives an error: 'WSL 2 installation is incomplete or kernel update required'. Containers will not start.",
        "category": "software", "priority": "medium", "status": "deflected",
        "user_email": "bob@company.com", "days_ago": 15,
        "ai_kb": "Slow Computer Performance & High CPU / Memory Usage",
        "ai_solution": "1. Open PowerShell as Administrator.\n2. Run 'wsl --update' to download the latest Linux kernel package.\n3. Run 'wsl --shutdown' then restart Docker Desktop.",
        "user_followup": "Running wsl --update updated the kernel and Docker started right up. Thanks!",
    },
    {
        "subject": "Excel freezing when calculating large financial workbook (50MB+)",
        "description": "Opening our quarterly financial reporting model causes Excel to hang on 'Calculating (4 Threads): 0%' and eventually crashes.",
        "category": "software", "priority": "medium", "status": "resolved",
        "user_email": "alice@company.com", "assigned_email": "charlie@company.com", "days_ago": 28,
        "tech_reply": "Upgraded user from 32-bit Office to 64-bit Microsoft 365 Apps for Enterprise. Disabled hardware graphics acceleration in Excel Advanced Options. Workbook now recalculates in under 4 seconds.",
    },
    {
        "subject": "Visual Studio Code language server consuming 100% CPU",
        "description": "VS Code causes the CPU to peg at 100% due to rg.exe (ripgrep) and tsserver indexing inside node_modules folders.",
        "category": "software", "priority": "low", "status": "deflected",
        "user_email": "bob@company.com", "days_ago": 40,
        "ai_kb": "Slow Computer Performance & High CPU / Memory Usage",
        "ai_solution": "1. Open VS Code Settings (Ctrl+,).\n2. Search 'files.watcherExclude' and ensure '**/node_modules/**' and '**/.git/**' are included.\n3. Restart VS Code.",
        "user_followup": "Added watcher exclusions and CPU usage immediately dropped to 2%.",
    },

    # ── Category 4: Access, Accounts & Identity ────────────────────────────
    {
        "subject": "How do I reset my company password?",
        "description": "My corporate password expired while I was on leave. I am locked out of my workstation and need instructions and a self-service link to reset my account.",
        "category": "access", "priority": "high", "status": "deflected",
        "user_email": "alice@company.com", "days_ago": 1,
        "ai_kb": "Password Reset & Account Unlock — Self-Service Portal",
        "ai_solution": "1. Navigate to https://reset.company.com on your phone or any web browser.\n2. Enter your email: alice@company.com.\n3. Authenticate with your Microsoft Authenticator push notification.\n4. Set a new password meeting policy rules (12+ characters, 1 number, 1 symbol).",
        "user_followup": "Reset password via self-service portal successfully. Logged back into workstation.",
    },
    {
        "subject": "Active Directory account locked after 5 failed password attempts",
        "description": "My account got locked out because my old phone was still attempting to fetch company email in the background with an old password.",
        "category": "access", "priority": "high", "status": "resolved",
        "user_email": "bob@company.com", "assigned_email": "admin@company.com", "days_ago": 3,
        "tech_reply": "Unlocked account 'bsmith' in Active Directory Domain Controller DC01. Cleared bad password count and terminated stale Exchange ActiveSync partnership.",
    },
    {
        "subject": "Need temporary MFA bypass passkey for replacement phone",
        "description": "I dropped and broke my phone over the weekend. I cannot receive Duo/Microsoft Authenticator push notifications and cannot log into Okta SSO.",
        "category": "access", "priority": "critical", "status": "resolved",
        "user_email": "alice@company.com", "assigned_email": "admin@company.com", "days_ago": 7,
        "tech_reply": "Verified user identity via manager video confirmation. Generated 24-hour temporary Access Pass (TAP) code and provisioned a physical YubiKey 5 NFC hardware token.",
    },
    {
        "subject": "Requesting JetBrains PyCharm Pro license allocation",
        "description": "Joined the data engineering team and require a JetBrains PyCharm Professional license for Python/Spark development.",
        "category": "access", "priority": "low", "status": "resolved",
        "user_email": "bob@company.com", "assigned_email": "admin@company.com", "days_ago": 16,
        "tech_reply": "Assigned license seat from JetBrains Enterprise Team License Server. Invitation email sent to bob@company.com.",
    },
    {
        "subject": "Need access to Finance SharePoint group folder",
        "description": "Transferred to the Financial Planning & Analysis department. Need Read/Write access to the 'FP&A Financial Reports 2026' SharePoint site and Teams channel.",
        "category": "access", "priority": "medium", "status": "resolved",
        "user_email": "alice@company.com", "assigned_email": "admin@company.com", "days_ago": 24,
        "tech_reply": "Manager approval received. Added user to AD Security Group 'SG-SharePoint-Finance-RW'. Permissions synced to Microsoft 365 group.",
    },
    {
        "subject": "BitLocker recovery key prompt appearing on every reboot",
        "description": "Every time I restart my Dell laptop, blue screen prompts: 'Enter the recovery key for this drive (BitLocker)'. Entering the 48-digit key works, but it repeats next reboot.",
        "category": "access", "priority": "high", "status": "resolved",
        "user_email": "bob@company.com", "assigned_email": "charlie@company.com", "days_ago": 38,
        "tech_reply": "TPM PCR 7 integrity measurement was corrupted following BIOS 1.14 update. Suspended BitLocker protection for 1 reboot, re-enabled TPM PCR validation profile, and updated BIOS firmware.",
    },

    # ── Category 5: 2025 Historical Tickets (Last Year) ───────────────────
    {
        "subject": "VPN client certificate renewal for 2025 fiscal year",
        "description": "Annual device user certificate on CORP-LAPTOP-W11-842 is scheduled to expire in 3 days. Need automated renewal via Intune SCEP.",
        "category": "network", "priority": "medium", "status": "closed",
        "user_email": "alice@company.com", "assigned_email": "marcus@company.com", "days_ago": 280,
        "tech_reply": "Pushed SCEP certificate renewal profile from Intune MDM. New RSA 2048 client certificate installed in CurrentUser\\My certificate store.",
    },
    {
        "subject": "Windows 10 to Windows 11 Enterprise migration upgrade",
        "description": "Requesting OS upgrade to Windows 11 Build 23H2 with enterprise BitLocker and WSL2 support.",
        "category": "software", "priority": "low", "status": "closed",
        "user_email": "bob@company.com", "assigned_email": "charlie@company.com", "days_ago": 310,
        "tech_reply": "Performed in-place upgrade via SCCM Task Sequence. User profile and application data migrated with zero downtime.",
    },
    {
        "subject": "Docking station USB audio DAC buzz noise",
        "description": "Connecting 3.5mm headphones to dock audio output results in high frequency ground loop buzz when charging.",
        "category": "hardware", "priority": "low", "status": "closed",
        "user_email": "alice@company.com", "assigned_email": "diana@company.com", "days_ago": 340,
        "tech_reply": "Fitted ground loop noise isolator to 3.5mm jack. Noise eliminated.",
    },
    {
        "subject": "Annual SOC2 Security Audit access log review",
        "description": "Generating quarterly access certification and privilege group membership reports for compliance review.",
        "category": "access", "priority": "medium", "status": "closed",
        "user_email": "bob@company.com", "assigned_email": "admin@company.com", "days_ago": 390,
        "tech_reply": "Extracted Entra ID role assignments and sign-in audit logs for Q3 2025. Exported signed CSV to compliance vault.",
    },
    {
        "subject": "Floor 2 network switch firmware update maintenance",
        "description": "Scheduled maintenance to patch Cisco Catalyst 9300 switch stack to IOS-XE 17.9.4.",
        "category": "network", "priority": "high", "status": "closed",
        "user_email": "alice@company.com", "assigned_email": "marcus@company.com", "days_ago": 420,
        "tech_reply": "Completed stack firmware upgrade at 02:00 UTC. Redundant power supplies and PoE budgets verified.",
    },
    {
        "subject": "Subscribed to Figma Enterprise Design system seat",
        "description": "Need UI design seat provisioned for product redesign initiative.",
        "category": "access", "priority": "low", "status": "closed",
        "user_email": "bob@company.com", "assigned_email": "admin@company.com", "days_ago": 450,
        "tech_reply": "Added user to Figma Enterprise Org and assigned design editor role.",
    },

    # ── Category 6: Older than 1 Year (>1 Year / 2024 & 2023) ──────────────
    {
        "subject": "Initial workstation onboarding and asset assignment",
        "description": "New employee onboarding: Provision primary Dell Latitude workstation, corporate email, and Slack account.",
        "category": "hardware", "priority": "medium", "status": "closed",
        "user_email": "alice@company.com", "assigned_email": "diana@company.com", "days_ago": 600,
        "tech_reply": "Provisioned laptop AST-84291 with Windows Enterprise image, enrolled in Intune MDM, and handed over at desk 304.",
    },
    {
        "subject": "Office 365 cloud tenant migration cutover",
        "description": "Migrating on-premises Exchange 2016 mailbox to Exchange Online hybrid cloud.",
        "category": "software", "priority": "high", "status": "closed",
        "user_email": "bob@company.com", "assigned_email": "marcus@company.com", "days_ago": 680,
        "tech_reply": "Mailbox migration batch completed (14.2 GB sync). Autodiscover pointed to outlook.office365.com.",
    },
    {
        "subject": "Core router fiber SFP transceiver replacement",
        "description": "Core router link to datacenter exhibiting optical RX power degradation (-24 dBm).",
        "category": "network", "priority": "critical", "status": "closed",
        "user_email": "alice@company.com", "assigned_email": "marcus@company.com", "days_ago": 750,
        "tech_reply": "Replaced 10G-LR SFP+ optical module on port TenGig0/1/1. Cleaned LC fiber connector with clicker. Optical power restored to -6.2 dBm.",
    },
    {
        "subject": "Legacy VPN PPTP deprecation and WireGuard pilot",
        "description": "Decommissioning legacy PPTP tunnels in favor of modern SSL/TLS endpoints.",
        "category": "network", "priority": "medium", "status": "closed",
        "user_email": "bob@company.com", "assigned_email": "charlie@company.com", "days_ago": 820,
        "tech_reply": "Decommissioned PPTP ports in perimeter firewall. Enforced TLS 1.3 on all corporate VPN concentrators.",
    },
    {
        "subject": "Disaster recovery failover test for Active Directory DC",
        "description": "Annual disaster recovery test: simulated loss of Primary Domain Controller DC01.",
        "category": "access", "priority": "high", "status": "closed",
        "user_email": "alice@company.com", "assigned_email": "admin@company.com", "days_ago": 900,
        "tech_reply": "Seized FSMO roles on DC02 successfully. DNS SRV records failed over within 45 seconds.",
    }
]

# Specific issues list for full variation
specific_issues = [
    ("Zoom video freezes when connecting bluetooth AirPods", "software", "low", "When joining Zoom calls with AirPods Pro 2 connected, video freezes for 5 seconds every time audio switches."),
    ("Slack desktop app shows blank screen with error DLG_FLAGS_INVALID_CA", "software", "medium", "Slack application window is completely blank white. Reloading with Ctrl+R fails to display channels."),
    ("Need AWS staging console access for RDS PostgreSQL database", "access", "high", "Need IAM permissions to connect to staging DB cluster via AWS IAM Database Authentication."),
    ("Wireless mouse cursor jumping erratically across screens", "hardware", "low", "Logitech MX Master 3S wireless mouse cursor stutters across screen when 2.4GHz USB receiver is plugged into monitor."),
    ("Cannot print PDF documents containing embedded barcodes", "hardware", "medium", "When printing shipping labels and invoices from Acrobat, barcode sections print as solid black blocks."),
    ("Node.js npm install fails with ETIMEDOUT fetching internal packages", "network", "high", "Running npm install against internal Artifactory registry times out. Need Artifactory SSL CA certificate installed."),
    ("Git push to GitHub Enterprise rejected due to pre-receive hook", "software", "medium", "Git push rejected with 'Secret scanning detected potential API key'. Need false positive secret pattern override."),
    ("Requesting Miro enterprise collaboration board license", "access", "low", "Our design sprint team requires 2 additional editor licenses on Miro Enterprise for upcoming roadmap planning."),
    ("Need local administrator rights for Wireshark packet capture", "access", "medium", "Need temporary privilege elevation to capture network packets on loopback interface for debugging microservices."),
    ("External USB 3.0 hard drive read-only error on macOS", "hardware", "low", "Seagate 4TB external backup drive mounts as Read-Only because it is formatted in NTFS. Need NTFS driver or exFAT reformat."),
    ("DNS leak detected when connected to split-tunnel VPN", "network", "medium", "Running DNS leak test shows local ISP DNS servers responding instead of corporate internal resolver 10.14.0.2."),
    ("Google Chrome browser managed by organization policy warning", "software", "low", "Chrome displays 'Managed by your organization' after installing corporate extension. Checking extension whitelist."),
    ("Keyring error on Ubuntu when storing Git credentials", "software", "medium", "Git credential helper reports 'gnome-keyring-daemon failed to unlock'. Need headless credential store setup."),
    ("Office 365 Excel macro workbook blocked by Mark of the Web", "software", "medium", "Opening vendor macro spreadsheet displays red security banner 'Microsoft has blocked macros from running'."),
    ("Need SSH key added to production bastion jump host", "access", "critical", "Requesting Ed25519 public key addition to /home/deploy/.ssh/authorized_keys on bastion01.corp.internal for deployment."),
    ("Secondary 144Hz gaming monitor stuck at 60Hz over HDMI", "hardware", "low", "Connecting monitor via HDMI cable limits refresh rate to 60Hz. Need DisplayPort 1.4 cable requisitioned."),
    ("Jira Software board failing to load backlog sprint items", "software", "low", "Jira sprint backlog shows loading spinner indefinitely. Clearing browser cache and cookies resolved it."),
    ("Need Okta Verify multi-factor authentication enrollment reset", "access", "high", "Transferred to a new phone and need Okta MFA enrollment email resent to re-pair push notifications."),
    ("Wi-Fi captive portal disconnects after 4 hours on guest network", "network", "low", "Contractor laptop requires extended 24-hour MAC address DHCP lease on Corp-Guest network."),
    ("Dell laptop keyboard spacebar physically sticking when pressed", "hardware", "low", "Spacebar key mechanism is sticky. Submitted hardware repair ticket for keyboard top-case replacement.")
]

now = datetime.utcnow()

# 1. Add primary raw tickets
for item in raw_tickets:
    user = alice if item["user_email"] == "alice@company.com" else bob
    assigned_email = item.get("assigned_email")
    assignee = users.get(assigned_email) if assigned_email else None
    
    created = now - timedelta(days=item.get("days_ago", 1), hours=random.randint(1, 12), minutes=random.randint(0, 59))
    resolved = (created + timedelta(hours=random.randint(2, 6))) if item["status"] in ("resolved", "closed", "deflected") else None
    dev = random.choice(devices)
    
    t = models.Ticket(
        user_id=user.id,
        subject=item["subject"],
        description=item["description"],
        category=item["category"],
        priority=item["priority"],
        status=item["status"],
        assigned_to=assignee.id if assignee else None,
        suggested_team=item["category"],
        tags=[item["category"]],
        device_name=dev["device_name"],
        device_os=dev["device_os"],
        ip_address=dev["ip_address"],
        subnet_vlan=dev["subnet_vlan"],
        mac_address=dev["mac_address"],
        asset_tag=dev["asset_tag"],
        serial_number=dev["serial_number"],
        last_reboot=dev["last_reboot"],
        edr_status=dev["edr_status"],
        hardware_specs=dev["hardware_specs"],
        domain_join=dev["domain_join"],
        office_location=dev["office_location"],
        sla_due=created + timedelta(hours=4),
        created_at=created,
        updated_at=created + timedelta(hours=1),
        resolved_at=resolved
    )
    db.add(t)
    db.flush()
    
    # User message
    db.add(models.TicketMessage(
        ticket_id=t.id,
        sender_type="user",
        sender_id=user.id,
        body=item["description"],
        created_at=created
    ))
    
    # AI response
    if item.get("ai_kb"):
        ai_msg = f"Based on our knowledge base article \"{item['ai_kb']}\", here are the recommended resolution steps:\n\n{item.get('ai_solution', '')}\n\nPlease try these steps. If this fixed your problem, click 'Yes, it\\'s fixed!' below."
        db.add(models.TicketMessage(
            ticket_id=t.id,
            sender_type="ai",
            body=ai_msg,
            created_at=created + timedelta(minutes=2)
        ))
        
    # User feedback
    if item.get("user_followup"):
        db.add(models.TicketMessage(
            ticket_id=t.id,
            sender_type="user",
            sender_id=user.id,
            body=item["user_followup"],
            created_at=created + timedelta(minutes=25)
        ))
        
    # Technician response
    if item.get("tech_reply") and assignee:
        db.add(models.TicketMessage(
            ticket_id=t.id,
            sender_type="technician",
            sender_id=assignee.id,
            body=item["tech_reply"],
            created_at=created + timedelta(hours=1, minutes=15)
        ))
        
    # Briefing
    if item["status"] in ("in_progress", "critical") or item["priority"] == "critical":
        db.add(models.HandoverBriefing(
            ticket_id=t.id,
            summary=f"User {user.name} reports: {item['subject']}. {item['description'][:120]}...",
            user_tried="User completed self-service troubleshooting without success.",
            ai_tried="AI diagnostic engine evaluated telemetry and provided targeted KB remediation.",
            likely_causes=["Hardware controller state", "System driver or service conflict", "Domain network / credential policy"],
            suggested_steps=[
                "Inspect device telemetry and ping host",
                "Execute SOP Playbook for targeted diagnostic",
                "Dispatch replacement hardware if component level failure is confirmed"
            ],
            related_ticket_ids=[f"#{t.id - 1}" if t.id > 1 else "#1"],
            generated_at=created + timedelta(minutes=5)
        ))

# 2. Add specific departmental tickets across the timeline
for i, (subj, cat, prio, desc) in enumerate(specific_issues):
    user = alice if i % 2 == 0 else bob
    tech = diana if cat == "hardware" else (charlie if cat == "network" else admin)
    
    days = (i * 35) + 3
    created = now - timedelta(days=days, hours=i * 2 + 1)
    status = "resolved" if days > 10 else ("in_progress" if i % 3 == 0 else "deflected")
    resolved = (created + timedelta(hours=3)) if status in ("resolved", "deflected") else None
    dev = devices[i % len(devices)]
    
    t = models.Ticket(
        user_id=user.id,
        subject=subj,
        description=desc,
        category=cat,
        priority=prio,
        status=status,
        assigned_to=tech.id,
        suggested_team=cat,
        tags=[cat],
        device_name=dev["device_name"],
        device_os=dev["device_os"],
        ip_address=dev["ip_address"],
        subnet_vlan=dev["subnet_vlan"],
        mac_address=dev["mac_address"],
        asset_tag=dev["asset_tag"],
        serial_number=dev["serial_number"],
        last_reboot=dev["last_reboot"],
        edr_status=dev["edr_status"],
        hardware_specs=dev["hardware_specs"],
        domain_join=dev["domain_join"],
        office_location=dev["office_location"],
        sla_due=created + timedelta(hours=4),
        created_at=created,
        updated_at=created + timedelta(hours=1),
        resolved_at=resolved
    )
    db.add(t)
    db.flush()
    
    db.add(models.TicketMessage(
        ticket_id=t.id,
        sender_type="user",
        sender_id=user.id,
        body=desc,
        created_at=created
    ))
    
    if status == "deflected":
        db.add(models.TicketMessage(
            ticket_id=t.id,
            sender_type="ai",
            body=f"AI Diagnostic Engine identified standard operating procedure for '{subj}'. Recommended remediation applied.",
            created_at=created + timedelta(minutes=2)
        ))
        db.add(models.TicketMessage(
            ticket_id=t.id,
            sender_type="user",
            sender_id=user.id,
            body="Confirmed that resolved the issue. Closing ticket.",
            created_at=created + timedelta(minutes=18)
        ))
    elif status in ("resolved", "closed"):
        db.add(models.TicketMessage(
            ticket_id=t.id,
            sender_type="technician",
            sender_id=tech.id,
            body=f"Investigated and resolved: verified '{subj}' is fully operational and device telemetry is nominal.",
            created_at=created + timedelta(hours=2)
        ))
        
    if status == "in_progress":
        db.add(models.HandoverBriefing(
            ticket_id=t.id,
            summary=f"Active Case: {subj}. Impacting user workstation {dev['device_name']}.",
            user_tried="User initiated triage.",
            ai_tried="Telemetry checked; ping latency normal.",
            likely_causes=["Software dependency", "Peripheral interface mismatch"],
            suggested_steps=["Run live diagnostic SOP", "Follow up with user via thread"],
            related_ticket_ids=[],
            generated_at=created + timedelta(minutes=5)
        ))

db.commit()
total_tickets = db.query(models.Ticket).count()
total_msgs = db.query(models.TicketMessage).count()
total_briefings = db.query(models.HandoverBriefing).count()

print(f"✅ Successfully populated {total_tickets} unique tickets with {total_msgs} messages and {total_briefings} briefings!")
db.close()
