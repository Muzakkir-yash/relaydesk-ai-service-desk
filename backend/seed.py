"""
Seed script — populates RelayDesk with realistic demo data.
Run: python seed.py
"""

import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, run_migrations
import models
from auth import hash_password
from datetime import datetime, timedelta
import json

run_migrations()

db = SessionLocal()

print("🌱 Seeding RelayDesk demo data...")

# ── Users ─────────────────────────────────────────────────────────
users_data = [
    {
        "name": "Alice Johnson",
        "email": "alice@company.com",
        "role": "enduser",
        "support_level": "L1",
        "primary_device": {
            "device_name": "CORP-LAPTOP-W11-842",
            "device_os": "Windows 11 Enterprise (Build 23H2)",
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
        }
    },
    {
        "name": "Bob Smith",
        "email": "bob@company.com",
        "role": "enduser",
        "support_level": "L1",
        "primary_device": {
            "device_name": "CORP-MBP-M3-104",
            "device_os": "macOS Sonoma 14.4.1 (Build 23E224)",
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
        }
    },
    {"name": "Diana Fix",     "email": "diana@company.com",  "role": "technician", "team": "hardware", "support_level": "L1"},
    {"name": "Charlie Tech",  "email": "charlie@company.com","role": "technician", "team": "network",  "support_level": "L2"},
    {"name": "Marcus Lead",   "email": "marcus@company.com", "role": "technician", "team": "infrastructure", "support_level": "L3"},
    {"name": "Eve Admin",     "email": "admin@company.com",  "role": "admin",      "team": "security", "support_level": "L3"},
]

users = {}
for u in users_data:
    existing = db.query(models.User).filter_by(email=u["email"]).first()
    if not existing:
        user = models.User(
            name=u["name"],
            email=u["email"],
            password_hash=hash_password("password123"),
            role=u["role"],
            team=u.get("team"),
            support_level=u.get("support_level", "L1"),
            primary_device=u.get("primary_device"),
        )
        db.add(user)
        db.flush()
        users[u["email"]] = user
    else:
        existing.support_level = u.get("support_level", "L1")
        if u.get("team"):
            existing.team = u["team"]
        if u.get("primary_device"):
            existing.primary_device = u["primary_device"]
        db.flush()
        users[u["email"]] = existing

db.commit()
print(f"  ✓ {len(users)} users synchronized")

# ── Major Incident Announcements ──────────────────────────────────
mim_announcements = [
    {
        "title": "⚠️ Major Incident MIM-2026-084: GlobalProtect VPN Gateway Intermittent Degradation",
        "message": "Users connecting from Europe & APAC gateways may experience intermittent TLS tunnel disconnects or handshake stalls. The Network Operations Center (NOC) is actively re-routing traffic to secondary cluster concentrators.",
        "severity": "warning",
        "is_active": False,  # demo incident starts resolved — no banner on a fresh install
        "affected_services": ["GlobalProtect VPN", "EMEA Core Gateway", "Zscaler Edge Connector"],
        "workaround": "In VPN Client Preferences, switch Gateway from 'EMEA-Auto' to 'US-East-Failover' or use the Web Access Portal.",
        "estimated_resolution": "11:45 AM EST (In ~30 mins)",
    },
    {
        "title": "🔧 Scheduled Maintenance: Active Directory Kerberos Realm Certificate Rotation",
        "message": "Quarterly certificate rotation on Domain Controllers DC01 & DC02. No user disruption expected. Technician password resets and SSO token provisioning will queue for up to 60 seconds.",
        "severity": "maintenance",
        "is_active": False,
        "affected_services": ["Active Directory Domain Services", "SSO Token Authority"],
        "workaround": "Technicians should use local cached credentials if provisioning encounters delay.",
        "estimated_resolution": "Completed (04:00 AM UTC)",
    }
]

for ann in mim_announcements:
    existing_ann = db.query(models.SystemAnnouncement).filter_by(title=ann["title"]).first()
    if not existing_ann:
        db.add(models.SystemAnnouncement(
            title=ann["title"],
            message=ann["message"],
            severity=ann["severity"],
            is_active=ann["is_active"],
            affected_services=ann["affected_services"],
            workaround=ann["workaround"],
            estimated_resolution=ann["estimated_resolution"],
            created_by_id=users["admin@company.com"].id if "admin@company.com" in users else None,
        ))
    else:
        existing_ann.message = ann["message"]
        existing_ann.is_active = ann["is_active"]
        existing_ann.workaround = ann["workaround"]
        existing_ann.affected_services = ann["affected_services"]
        existing_ann.estimated_resolution = ann["estimated_resolution"]

db.commit()
print(f"  ✓ Major Incident Announcements synchronized")

# ── KB Articles ───────────────────────────────────────────────────
kb_articles = [
    {
        "title": "Wi-Fi & Wireless Network Connection Troubleshooting",
        "body": (
            "If your laptop or computer cannot connect to the company Wi-Fi network:\n"
            "1. Verify that Wi-Fi is turned ON (check Windows taskbar Wi-Fi icon or physical Wi-Fi switch / Airplane Mode).\n"
            "2. Disconnect and reconnect to the official network: Select 'Company-Corp-Secure' or 'Company-Guest'.\n"
            "3. Forget the Wi-Fi network and reconnect: Windows Settings → Network & Internet → Wi-Fi → Manage Known Networks → Select 'Company-Corp-Secure' → Click 'Forget'. Then click on the network list, connect again, and enter your domain credentials.\n"
            "4. Restart your Wi-Fi Network Adapter:\n"
            "   - Press Windows Key + R, type 'ncpa.cpl', and press Enter.\n"
            "   - Right-click 'Wi-Fi' (Wireless Network Adapter) → click 'Disable'.\n"
            "   - Wait 10 seconds, right-click 'Wi-Fi' again → click 'Enable'.\n"
            "5. Release and renew IP & flush DNS:\n"
            "   - Press Windows Key, type 'cmd', right-click Command Prompt → 'Run as Administrator'.\n"
            "   - Run: ipconfig /release\n"
            "   - Run: ipconfig /renew\n"
            "   - Run: ipconfig /flushdns\n"
            "6. Restart your laptop to clear any cached network states.\n"
            "7. If other devices also cannot connect, the local Access Point may be experiencing an outage — contact the Network Operations team."
        ),
        "tags": "wifi wireless wlan ssid internet connection network signal adapter disconnect lap laptop",
    },
    {
        "title": "VPN Connection Issues — Troubleshooting Guide",
        "body": (
            "If you cannot connect to the company VPN:\n"
            "1. Ensure you have a stable internet connection.\n"
            "2. Open the VPN client (Cisco AnyConnect / GlobalProtect) and click Disconnect, then Connect again.\n"
            "3. Check that your VPN credentials haven't expired (reset at portal.company.com).\n"
            "4. Try switching from UDP to TCP in VPN client preferences.\n"
            "5. Restart the VPN service: Windows Services (services.msc) → Cisco AnyConnect / VPN Agent → Restart.\n"
            "6. If on Windows, flush DNS: open Command Prompt as Admin and run 'ipconfig /flushdns'.\n"
            "7. If none of the above work, contact the network team."
        ),
        "tags": "vpn cisco anyconnect tunnel remote gateway anyconnect vpn-client secure-connection",
    },
    {
        "title": "Password Reset & Account Unlock — Self-Service Portal",
        "body": (
            "To reset your password or unlock your account:\n"
            "1. Visit https://reset.company.com on any browser or mobile device.\n"
            "2. Enter your corporate email address (e.g. username@company.com).\n"
            "3. Complete the MFA verification code sent to your registered authenticator app or phone.\n"
            "4. Set a new password meeting policy requirements: 12+ characters, uppercase, lowercase, number, and special character.\n"
            "5. Log in with your new password on your workstation.\n"
            "Note: If your account was locked due to failed attempts, please wait 15 minutes before retrying."
        ),
        "tags": "password reset account access login credentials expired lockout unlock sso",
    },
    {
        "title": "Multi-Factor Authentication (MFA / 2FA) & Authenticator App Issues",
        "body": (
            "If you are not receiving MFA prompts or your verification codes are failing:\n"
            "1. Check time synchronization on your phone: Settings → Date & Time → toggle 'Set Automatically' to ON (out-of-sync clocks break OTP codes).\n"
            "2. Ensure your phone has an active internet connection (Wi-Fi or cellular data) to receive push notifications.\n"
            "3. Open the Microsoft Authenticator or Duo app directly and manually check for pending approval requests.\n"
            "4. Use the 'Sign in another way' link on the login screen to receive an SMS or phone call code instead.\n"
            "5. If you changed your phone or lost access to your authenticator device, contact the IT Access Management team for a temporary passkey."
        ),
        "tags": "mfa 2fa authenticator duo microsoft phone code otp token verify signin login",
    },
    {
        "title": "Laptop Won't Turn On — Hardware Troubleshooting",
        "body": (
            "Steps when laptop fails to power on or shows a black screen:\n"
            "1. Perform a hard reset: Hold the power button down for 15 seconds to force shutdown, wait 10 seconds, then press power again.\n"
            "2. Disconnect from any docking station, external monitors, and USB hubs. Plug the OEM charger directly into the laptop.\n"
            "3. Verify the charger LED light is on. Try a different wall outlet directly without surge strips.\n"
            "4. If the laptop has a removable battery, remove it, hold the power button for 30 seconds to drain residual static, reinsert, and power on.\n"
            "5. If the keyboard lights up or fans spin but the screen is dark, press Windows Key + Ctrl + Shift + B to restart the graphics driver.\n"
            "6. Connect an external monitor via HDMI to verify if the issue is display-specific.\n"
            "7. If the power LED blinks an error code pattern, note it and submit a hardware replacement request."
        ),
        "tags": "laptop hardware power boot won't start black screen battery charging adapter no display",
    },
    {
        "title": "External Monitor & Dual Display Configuration Issues",
        "body": (
            "If your external monitor is not detected, flickering, or displaying incorrect resolution:\n"
            "1. Press Windows Key + P and ensure 'Extend' or 'Duplicate' is selected.\n"
            "2. Reseat video cables firmly (HDMI / DisplayPort / USB-C) at both the monitor and the laptop/dock ends.\n"
            "3. Power cycle the docking station: Unplug the dock power cable for 15 seconds, reconnect, and plug the USB-C cable back in.\n"
            "4. Reset the graphics subsystem by pressing: Windows Key + Ctrl + Shift + B (the screen will blink and beep briefly).\n"
            "5. Go to Windows Settings → System → Display → Multiple Displays → click 'Detect'.\n"
            "6. Check monitor input source: Press the physical menu button on the monitor and ensure the correct input (HDMI 1, DP 1) is selected."
        ),
        "tags": "monitor display screen second screen dual monitor hdmi displayport dock flickering resolution no signal",
    },
    {
        "title": "Microsoft Teams & Zoom Audio / Video / Microphone Troubleshooting",
        "body": (
            "Fix audio, microphone, or camera problems in Teams or Zoom:\n"
            "1. In Teams: Click '...' (Settings) → Devices → select your correct headset/microphone and speaker from the dropdowns.\n"
            "2. Test your setup: In Teams Device Settings, click 'Make a test call' to verify audio playback and recording.\n"
            "3. Check Windows microphone privacy: Windows Settings → Privacy & Security → Microphone → Ensure 'Let apps access your microphone' is turned ON.\n"
            "4. Check the physical mute switch on your headset cord or boom microphone.\n"
            "5. Fully restart the app: Right-click Teams in the taskbar system tray → click 'Quit', then reopen Teams.\n"
            "6. If video is black, check that the physical webcam privacy shutter is open."
        ),
        "tags": "teams zoom audio video microphone mic speaker camera webcam meeting call sound",
    },
    {
        "title": "Microsoft Outlook & Corporate Email Sync / Password Prompt Issues",
        "body": (
            "If Outlook is disconnected, repeatedly asking for a password, or not syncing emails:\n"
            "1. Check the bottom right status bar in Outlook: if it says 'Disconnected' or 'Need Password', click on it to re-authenticate.\n"
            "2. Clear stored Office credentials:\n"
            "   - Open Windows Control Panel → Credential Manager → Windows Credentials.\n"
            "   - Under Generic Credentials, remove entries starting with 'MicrosoftOffice16' or 'MS.Outlook'.\n"
            "   - Restart Outlook and enter your company credentials when prompted.\n"
            "3. Start Outlook in Safe Mode to disable buggy add-ins: Press Win+R, type 'outlook.exe /safe', and press Enter.\n"
            "4. Perform an Office Quick Repair: Windows Settings → Apps → Installed Apps → Microsoft 365 Apps → Modify → Quick Repair.\n"
            "5. Access your mailbox via webmail (https://outlook.office.com) to verify your account is active."
        ),
        "tags": "outlook email mail mailbox exchange inbox calendar sync password prompt send receive disconnected",
    },
    {
        "title": "Network Printer Not Found or Printer Offline",
        "body": (
            "To reconnect to a network printer or clear stuck print jobs:\n"
            "1. Open Windows Settings → Bluetooth & Devices → Printers & Scanners → Select your printer.\n"
            "2. Open Print Queue: Click 'Open print queue' → Printer menu → Cancel all documents.\n"
            "3. Restart the Windows Print Spooler service:\n"
            "   - Press Win+R, type 'cmd', press Ctrl+Shift+Enter for Administrator.\n"
            "   - Run: net stop spooler\n"
            "   - Run: net start spooler\n"
            "4. If printer is offline, verify the printer's physical power light and network cable are connected.\n"
            "5. Re-add the printer: Click 'Add device' → 'The printer that I want isn't listed' → 'Add a printer using an IP address' and enter the printer's IP found on its front panel."
        ),
        "tags": "printer network offline driver hardware printing print spooler queue paper jam",
    },
    {
        "title": "Slow Computer Performance & High CPU / Memory Usage",
        "body": (
            "If your computer is lagging, freezing, or running unusually slow:\n"
            "1. Open Task Manager: Press Ctrl + Shift + Esc.\n"
            "2. Sort by 'CPU' and 'Memory' columns to identify background processes consuming excessive resources. Right-click unresponsive apps → 'End task'.\n"
            "3. Disable unnecessary startup programs: Task Manager → 'Startup apps' tab → Disable non-essential applications.\n"
            "4. Free up disk space: Press Win+R, type 'cleanmgr', press Enter → select C: drive → check 'Temporary files' and click OK.\n"
            "5. Check for pending Windows Updates: Windows Settings → Windows Update → Check for updates, then restart your PC.\n"
            "6. Run System File Checker: Open Command Prompt as Admin and run 'sfc /scannow'."
        ),
        "tags": "slow performance lagging freeze high cpu memory disk task manager cleanup startup ram unresponsive",
    },
    {
        "title": "Blue Screen of Death (BSOD) & Windows System Crashes",
        "body": (
            "If your computer encountered a Blue Screen crash (BSOD) or keeps restarting:\n"
            "1. Note the Stop Code displayed on the blue screen (e.g. CRITICAL_PROCESS_DIED, DPC_WATCHDOG_VIOLATION, MEMORY_MANAGEMENT).\n"
            "2. Disconnect any newly attached external USB devices or docks to isolate hardware conflicts.\n"
            "3. Run Windows System File repair tools:\n"
            "   - Open Command Prompt (Admin) and run:\n"
            "     DISM.exe /Online /Cleanup-image /Restorehealth\n"
            "     sfc /scannow\n"
            "4. Run Windows Memory Diagnostic: Press Win+R, type 'mdsched.exe', press Enter, and select 'Restart now and check for problems'.\n"
            "5. Ensure graphics and chipset drivers are updated via Dell Command / Lenovo Vantage / HP Support Assistant.\n"
            "6. If the crash happens repeatedly, our technicians can analyze the minidump file located at C:\\Windows\\Minidump."
        ),
        "tags": "bsod blue screen crash dump restart kernel dump stop code memory dump error bugcheck",
    },
    {
        "title": "Shared Network Drives, OneDrive & SharePoint Access Issues",
        "body": (
            "If you cannot access mapped network drives (e.g. Z: drive) or shared folders:\n"
            "1. If working remotely, verify that your corporate VPN is connected first.\n"
            "2. Test direct server connection: Press Win+R, type '\\\\fileserver.company.internal\\share', and press Enter.\n"
            "3. Remap the network drive:\n"
            "   - Open File Explorer → This PC → '...' → Map network drive.\n"
            "   - Select the drive letter, enter the folder path, and check 'Reconnect at sign-in'.\n"
            "4. If receiving an 'Access Denied' error, your Active Directory security group permissions may need updating by your department manager.\n"
            "5. For OneDrive sync issues: Right-click OneDrive cloud icon in the taskbar → Settings → Pause syncing for 2 hours, then Resume."
        ),
        "tags": "shared drive mapped drive network drive sharepoint onedrive file access permission folder path z drive network-share",
    },
]

for kba in kb_articles:
    existing = db.query(models.KBArticle).filter_by(title=kba["title"]).first()
    if not existing:
        db.add(models.KBArticle(**kba))
    else:
        existing.body = kba["body"]
        existing.tags = kba["tags"]

db.commit()
print(f"  ✓ {len(kb_articles)} KB articles synchronized")

# ── SLA Policies ──────────────────────────────────────────────────
sla_data = [
    {"priority": "critical", "response_minutes": 15,  "resolution_minutes": 60},
    {"priority": "high",     "response_minutes": 60,  "resolution_minutes": 240},
    {"priority": "medium",   "response_minutes": 240, "resolution_minutes": 480},
    {"priority": "low",      "response_minutes": 480, "resolution_minutes": 1440},
]
for s in sla_data:
    if not db.query(models.SLAPolicy).filter_by(priority=s["priority"]).first():
        db.add(models.SLAPolicy(**s))
db.commit()
print("  ✓ SLA policies")

# ── Demo Tickets ──────────────────────────────────────────────────
# Update existing tickets if they don't have device metadata
existing_tickets = db.query(models.Ticket).all()
for t in existing_tickets:
    submitter = t.submitter
    dev = (submitter.primary_device if submitter else None) or {
        "device_name": "CORP-LAPTOP-W11-842",
        "device_os": "Windows 11 Enterprise (Build 23H2)",
        "ip_address": "10.14.88.24",
        "subnet_vlan": "VLAN 20 (HQ Floor 3 - Engineering)",
        "mac_address": "00:1A:2B:3C:4D:5E",
        "asset_tag": "AST-84291",
        "serial_number": "PF39X8K2",
        "last_reboot": "3 days ago (Uptime: 74h 12m)",
        "edr_status": "CrowdStrike Falcon (Healthy / v7.14.0)",
        "hardware_specs": "Intel Core i7-1370P | 32 GB RAM | 512 GB NVMe",
        "domain_join": "CORP.INTERNAL (Azure AD Hybrid / Intune Compliant)",
        "office_location": "HQ - Building B - Desk 304",
    }
    if not t.device_name:
        t.device_name = dev["device_name"]
        t.device_os = dev["device_os"]
        t.ip_address = dev["ip_address"]
        t.subnet_vlan = dev["subnet_vlan"]
        t.mac_address = dev["mac_address"]
        t.asset_tag = dev["asset_tag"]
        t.serial_number = dev["serial_number"]
        t.last_reboot = dev["last_reboot"]
        t.edr_status = dev["edr_status"]
        t.hardware_specs = dev["hardware_specs"]
        t.domain_join = dev["domain_join"]
        t.office_location = dev["office_location"]

db.commit()

# Guard: skip if tickets already exist (safe to re-run seed.py)
if len(existing_tickets) > 0:
    print(f"  ℹ {len(existing_tickets)} existing tickets updated with enterprise device context.")
    db.close()
    print("\n✅ Seeding complete! Demo credentials:")
    print("   alice@company.com   / password123  (end user)")
    print("   charlie@company.com / password123  (technician)")
    print("   admin@company.com   / password123  (admin)")
    exit(0)

demo_tickets = [
    {
        "subject": "Cannot connect to VPN from home",
        "description": "I've been trying to connect to the company VPN since this morning but it keeps timing out. I need access for an urgent client presentation.",
        "category": "network", "priority": "high", "status": "deflected",
        "user_email": "alice@company.com",
    },
    {
        "subject": "Password expired and locked out",
        "description": "My password expired and I tried to reset it but the reset email never arrived. I cannot log in to any company systems.",
        "category": "account", "priority": "high", "status": "resolved",
        "user_email": "bob@company.com",
        "assigned_email": "charlie@company.com",
    },
    {
        "subject": "Laptop screen is completely black",
        "description": "My Dell laptop won't turn on at all. The power LED briefly blinks 3 times then nothing. This started after a Windows update last night.",
        "category": "hardware", "priority": "critical", "status": "in_progress",
        "user_email": "alice@company.com",
        "assigned_email": "diana@company.com",
    },
    {
        "subject": "Teams microphone not working in meetings",
        "description": "My microphone stopped working in Microsoft Teams. Other participants cannot hear me. The microphone works fine in other apps like Zoom.",
        "category": "software", "priority": "medium", "status": "deflected",
        "user_email": "bob@company.com",
    },
    {
        "subject": "Printer shows offline in the accounting office",
        "description": "The shared HP printer on floor 2 shows as offline for everyone in accounting. We have end-of-month reports to print urgently.",
        "category": "hardware", "priority": "high", "status": "escalated",
        "user_email": "alice@company.com",
    },
]

now = datetime.utcnow()
for i, td in enumerate(demo_tickets):
    user = users[td["user_email"]]
    assigned = users.get(td.get("assigned_email", "")) if td.get("assigned_email") else None
    created = now - timedelta(hours=i * 8 + 2)
    resolved = (created + timedelta(hours=4)) if td["status"] in ("resolved", "deflected") else None
    dev = user.primary_device or {}

    ticket = models.Ticket(
        user_id=user.id,
        subject=td["subject"],
        description=td["description"],
        category=td["category"],
        priority=td["priority"],
        status=td["status"],
        assigned_to=assigned.id if assigned else None,
        suggested_team="network" if td["category"] == "network" else td["category"],
        tags=[td["category"]],
        device_name=dev.get("device_name", "CORP-LAPTOP-W11-842"),
        device_os=dev.get("device_os", "Windows 11 Enterprise (Build 23H2)"),
        ip_address=dev.get("ip_address", "10.14.88.24"),
        subnet_vlan=dev.get("subnet_vlan", "VLAN 20 (HQ Floor 3 - Engineering)"),
        mac_address=dev.get("mac_address", "00:1A:2B:3C:4D:5E"),
        asset_tag=dev.get("asset_tag", "AST-84291"),
        serial_number=dev.get("serial_number", "PF39X8K2"),
        last_reboot=dev.get("last_reboot", "3 days ago (Uptime: 74h 12m)"),
        edr_status=dev.get("edr_status", "CrowdStrike Falcon (Healthy / v7.14.0)"),
        hardware_specs=dev.get("hardware_specs", "Intel Core i7-1370P | 32 GB RAM | 512 GB NVMe"),
        domain_join=dev.get("domain_join", "CORP.INTERNAL (Azure AD Hybrid / Intune Compliant)"),
        office_location=dev.get("office_location", "HQ - Building B - Desk 304"),
        sla_due=created + timedelta(hours=4),
        created_at=created,
        updated_at=created + timedelta(hours=1),
        resolved_at=resolved,
    )
    db.add(ticket)
    db.flush()

    # Add initial message
    db.add(models.TicketMessage(
        ticket_id=ticket.id,
        sender_type="user",
        sender_id=user.id,
        body=td["description"],
        created_at=created,
    ))

    # Add AI message for deflected tickets
    if td["status"] == "deflected":
        db.add(models.TicketMessage(
            ticket_id=ticket.id,
            sender_type="ai",
            body="I found some relevant steps in our knowledge base that might help. Please try the steps below and let me know if they resolve your issue.",
            created_at=created + timedelta(minutes=2),
        ))
        db.add(models.TicketMessage(
            ticket_id=ticket.id,
            sender_type="user",
            sender_id=user.id,
            body="That fixed it! Thank you!",
            created_at=created + timedelta(minutes=30),
        ))

    # Add a briefing for escalated tickets
    if td["status"] in ("escalated", "in_progress", "critical"):
        db.add(models.HandoverBriefing(
            ticket_id=ticket.id,
            summary=f"User {user.name} reports: {td['subject']}. Issue started recently and is impacting their work.",
            user_tried="User attempted basic restart and reconnection steps with no improvement.",
            ai_tried="AI searched the knowledge base and provided standard troubleshooting steps which did not resolve the issue.",
            likely_causes=["Driver or firmware issue", "Hardware failure", "Network/permission configuration"],
            suggested_steps=[
                "Verify device/service status in admin console",
                "Remote into user machine to inspect logs",
                "Escalate to hardware team if software-level fix is not possible",
            ],
            related_ticket_ids=["#1 — VPN fixed by reinstalling Cisco AnyConnect client"],
            generated_at=created + timedelta(minutes=5),
        ))

db.commit()
print(f"  ✓ {len(demo_tickets)} demo tickets with messages and briefings")

db.close()
print("\n✅ Seeding complete! Demo credentials:")
print("   alice@company.com   / password123  (end user)")
print("   charlie@company.com / password123  (technician)")
print("   admin@company.com   / password123  (admin)")
