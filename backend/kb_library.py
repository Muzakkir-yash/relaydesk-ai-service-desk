"""
Built-in knowledge-base library for the offline support chatbot.

Each article covers one everyday IT problem: a one-line symptom, numbered
steps an employee can follow without admin rights, and when to escalate.
Tags hold the words people actually type for the problem (including common
misspellings) because the chatbot finds articles by title and tag words.

seed.py loads these into the database; main.py also adds any that are
missing on start-up, so a fresh install answers these problems out of the box.
"""

from typing import Dict, List

KB_LIBRARY: List[Dict[str, str]] = [
    # ── Hardware ──────────────────────────────────────────────────────
    {
        "title": "Webcam / Camera Not Working",
        "category": "hardware",
        "body": (
            "If your camera shows a black screen, a slashed camera icon, or 'We can't find your camera':\n"
            "1. Check for a privacy shutter sliding over the lens, and for a camera key on the keyboard (often F8/F10 or a key with a camera icon) — press it once.\n"
            "2. Turn on camera access: Windows Settings → Privacy & Security → Camera → switch ON 'Camera access' and 'Let apps access your camera' (and 'Let desktop apps access your camera').\n"
            "3. Close every other app that may be using the camera (Teams, Zoom, browser tabs) — only one app can use it at a time.\n"
            "4. Open the Windows Camera app. If the picture works there, choose the right camera in your meeting app: Teams → Settings → Devices → Camera.\n"
            "5. External USB webcam: unplug it and plug it straight into another USB port on the laptop (not a hub or the dock).\n"
            "6. Reset the driver: right-click Start → Device Manager → Cameras → right-click your camera → Uninstall device, then restart the PC.\n"
            "If the camera is missing from Device Manager after a restart, contact IT — it may be a hardware fault."
        ),
        "tags": "camera webcam web cam video black screen camera not detected cant find camera slashed camera privacy shutter teams camera zoom video",
    },
    {
        "title": "Laptop Battery Not Charging or Draining Fast",
        "category": "hardware",
        "body": (
            "If the battery icon says 'Plugged in, not charging', the laptop dies on battery quickly, or the charger light is off:\n"
            "1. Check the charger: make sure both ends are pushed in fully, try a different wall socket, and look for a light on the charger brick or port.\n"
            "2. USB-C chargers: try the other USB-C port — only some ports accept power. Use the company charger; phone chargers are too weak.\n"
            "3. Restart the laptop with the charger connected.\n"
            "4. Check battery health: open Command Prompt and run 'powercfg /batteryreport', then open the battery-report.html file it creates and compare 'Full charge capacity' with 'Design capacity'.\n"
            "5. Make the battery last longer: Windows Settings → System → Power & battery → turn on Battery saver and set Power mode to 'Best power efficiency'; lower screen brightness.\n"
            "6. See what is using power: Settings → System → Power & battery → Battery usage, and close the heavy apps.\n"
            "If the battery is swollen (case bulging, touchpad lifting) stop using the laptop and contact IT immediately. For a faulty charger or a battery below 50% capacity, raise a ticket for a replacement."
        ),
        "tags": "battery charging charger not charging plugged in not charging battery drain draining dies fast power adapter usb-c charger battery health low battery",
    },
    {
        "title": "Laptop Overheating or Fan Very Loud",
        "category": "hardware",
        "body": (
            "If the laptop is hot to touch, the fan is loud all the time, or it slows down or shuts off when hot:\n"
            "1. Put the laptop on a hard, flat surface — beds, sofas and laps block the air vents.\n"
            "2. Check what is working the processor: press Ctrl+Shift+Esc → Task Manager → sort by CPU and close apps you don't need.\n"
            "3. Close unused browser tabs and stop videos playing in the background.\n"
            "4. Set Power mode to 'Balanced': Windows Settings → System → Power & battery → Power mode.\n"
            "5. Restart the laptop — a stuck background process often keeps the fan running.\n"
            "6. Make sure the vents (sides and bottom) are not covered or visibly dusty.\n"
            "If it shuts itself off from heat or the fan rattles or grinds, contact IT — the fan may need cleaning or replacing."
        ),
        "tags": "overheating overheat hot heating up fan loud fan noise noisy fan laptop hot temperature thermal shuts down when hot",
    },
    {
        "title": "Keyboard Not Working or Typing Wrong Characters",
        "category": "hardware",
        "body": (
            "If keys don't respond, type the wrong symbols (for example @ and \" swapped), or keys stick:\n"
            "1. Wrong symbols: the keyboard layout changed. Press Windows Key + Space to switch layout, or go to Windows Settings → Time & Language → Language & region and remove the layouts you don't use.\n"
            "2. Numbers not typing on the number pad: press Num Lock. Everything in CAPITALS: press Caps Lock.\n"
            "3. Keys do nothing or lag: Windows Settings → Accessibility → Keyboard → turn OFF Sticky Keys and Filter Keys.\n"
            "4. External USB keyboard: unplug it and plug into another USB port. Wireless keyboard: replace the batteries and re-insert the USB receiver; Bluetooth keyboard: remove and re-pair it.\n"
            "5. Restart the PC. If the laptop keyboard still doesn't work, plug in a USB keyboard to keep working.\n"
            "6. Sticky or crumb-filled keys: shut down and gently clean around the keys with compressed air.\n"
            "If keys are physically damaged or liquid was spilled, switch off the laptop and contact IT."
        ),
        "tags": "keyboard keys not working typing wrong characters wrong symbols layout keys stuck sticky keys num lock caps lock wireless keyboard typing shift @ at sign quote symbol instead pound hash",
    },
    {
        "title": "Mouse or Touchpad Not Working",
        "category": "hardware",
        "body": (
            "If the pointer doesn't move, jumps around, or clicks don't work:\n"
            "1. Touchpad: press the touchpad key (often F6 or a key with a touchpad icon). Then check Windows Settings → Bluetooth & devices → Touchpad → make sure Touchpad is ON.\n"
            "2. Wireless mouse: replace the battery, switch it off and on, and re-insert the USB receiver into another port.\n"
            "3. Bluetooth mouse: Settings → Bluetooth & devices → remove the mouse, then add it again.\n"
            "4. Wired mouse: try another USB port (not a hub).\n"
            "5. Jumpy pointer: clean the mouse sensor and use it on a mouse mat, not glass or glossy desks.\n"
            "6. Restart the PC. You can still navigate with the keyboard: Tab, arrow keys and Enter.\n"
            "If it still doesn't work with a second mouse, contact IT."
        ),
        "tags": "mouse touchpad trackpad pointer cursor not moving cursor jumping click not working wireless mouse bluetooth mouse clicking",
    },
    {
        "title": "Bluetooth Device Won't Connect or Pair",
        "category": "hardware",
        "body": (
            "If Bluetooth headphones, a mouse, keyboard or speaker won't connect:\n"
            "1. Make sure Bluetooth is ON: Windows Settings → Bluetooth & devices → Bluetooth.\n"
            "2. Charge the device and put it in pairing mode (usually hold the power or Bluetooth button until a light flashes).\n"
            "3. Remove the old pairing: Settings → Bluetooth & devices → click the device → Remove device. Then 'Add device' → Bluetooth and pick it.\n"
            "4. Disconnect it from your phone or other computers — many devices only connect to one at a time.\n"
            "5. Turn Bluetooth off and on, or restart the PC.\n"
            "6. If the Bluetooth switch is missing: right-click Start → Device Manager → Bluetooth → right-click the adapter → Enable device.\n"
            "If the device works on another computer but never on yours, contact IT."
        ),
        "tags": "bluetooth pair pairing wont connect airpods headphones earbuds bluetooth headset bluetooth speaker bluetooth missing",
    },
    {
        "title": "No Sound from Speakers or Headphones",
        "category": "hardware",
        "body": (
            "If you can't hear anything from the computer:\n"
            "1. Check the volume: click the speaker icon in the taskbar and make sure it isn't muted. Check the mute key on the keyboard too.\n"
            "2. Pick the right output: click the speaker icon → the arrow next to the volume → choose your speakers or headphones.\n"
            "3. Check the app's own volume: Windows Settings → System → Sound → Volume mixer.\n"
            "4. Wired headphones: unplug and plug them in fully. USB headset: try another USB port. Bluetooth: see the Bluetooth article.\n"
            "5. Run the fixer: Windows Settings → System → Troubleshoot → Other troubleshooters → Audio → Run.\n"
            "6. Restart the PC.\n"
            "For sound problems only in meetings, select your device in Teams → Settings → Devices. If there's still no sound, contact IT."
        ),
        "tags": "sound no sound audio speakers speaker headphones earphones volume muted cant hear audio not working no audio",
    },
    {
        "title": "USB Device Not Recognized",
        "category": "hardware",
        "body": (
            "If a USB drive, headset or other device does nothing or shows 'USB device not recognized':\n"
            "1. Unplug it, wait 10 seconds, and plug it straight into a different USB port on the computer (not a hub or extension cable).\n"
            "2. Try the device on another computer to see if the device itself is faulty.\n"
            "3. Restart the PC with the device unplugged, then plug it in again.\n"
            "4. Reset the port: right-click Start → Device Manager → Universal Serial Bus controllers → right-click the device with a warning icon → Uninstall device, then restart.\n"
            "5. USB storage drives: company policy may block personal USB drives. Use OneDrive to move files instead.\n"
            "Never plug in a USB stick you found — report it to IT security."
        ),
        "tags": "usb usb device not recognized usb drive flash drive pen drive usb stick usb port not working external hard drive",
    },
    {
        "title": "Docking Station or USB-C Dock Not Working",
        "category": "hardware",
        "body": (
            "If monitors, keyboard, network or charging stop working through the dock:\n"
            "1. Unplug the dock's power adapter for 15 seconds, plug it back in, then reconnect the USB-C / Thunderbolt cable to the laptop.\n"
            "2. Use the correct port on the laptop — the one with a lightning-bolt (Thunderbolt) or DisplayPort symbol.\n"
            "3. Make sure the dock's own power adapter is connected; the laptop cable alone can't power the dock.\n"
            "4. Restart the laptop while docked.\n"
            "5. Check for updates: Windows Settings → Windows Update, and install any Dell/Lenovo/HP dock firmware offered through Company Portal.\n"
            "6. Plug a monitor straight into the laptop to see whether the dock or the monitor is the problem.\n"
            "If the dock has no lights at all with power connected, contact IT for a replacement."
        ),
        "tags": "dock docking station usb-c dock thunderbolt dock dock not working docked monitors not working through dock port replicator",
    },
    {
        "title": "Laptop Screen Problems: Dim, Upside Down, Blurry or Wrong Size",
        "category": "hardware",
        "body": (
            "If the built-in screen is too dark, rotated, blurry or everything looks too big or small:\n"
            "1. Too dark: press the brightness keys (often F1/F2 or keys with a sun icon), or Windows Settings → System → Display → Brightness. Turn off 'Change brightness based on content' if it keeps dimming.\n"
            "2. Upside down or sideways: Settings → System → Display → Display orientation → Landscape. On some PCs Ctrl+Alt+Up Arrow also fixes it.\n"
            "3. Everything too big or small: Settings → System → Display → Scale → choose the 'Recommended' value.\n"
            "4. Blurry text: Settings → System → Display → Display resolution → choose the 'Recommended' resolution.\n"
            "5. Yellow tint: Settings → System → Display → turn off Night light.\n"
            "6. Flickering or lines: restart the graphics driver with Windows Key + Ctrl + Shift + B, then restart the PC.\n"
            "If there are cracks, permanent lines or dead areas on the screen, contact IT — it's a hardware repair."
        ),
        "tags": "screen brightness dim dark screen screen upside down rotated sideways blurry text too big too small scaling resolution night light yellow screen lines on screen",
    },
    {
        "title": "Scanner or Scan-to-Email Not Working",
        "category": "hardware",
        "body": (
            "If the office copier won't scan to your email or a scanner isn't found:\n"
            "1. Check the email address typed on the copier screen — pick yourself from the address book rather than typing it.\n"
            "2. Large scans may be blocked by size limits: scan fewer pages at a time or choose a lower resolution (200–300 dpi) and black & white.\n"
            "3. Look in your Junk Email folder in Outlook for the scan.\n"
            "4. Desktop scanner: unplug and reconnect the USB cable, then open the Windows Scan app or Windows Settings → Bluetooth & devices → Printers & scanners.\n"
            "5. Restart the scanner or copier if its screen shows an error.\n"
            "If scanning fails for everyone on that copier, raise a ticket with the copier's name or asset tag."
        ),
        "tags": "scanner scan scanning scan to email copier photocopier scan not working scanned document not received multifunction",
    },
    {
        "title": "Meeting Room Screen, Projector or TV Not Showing Laptop",
        "category": "hardware",
        "body": (
            "If the meeting room screen shows 'No signal' when you connect your laptop:\n"
            "1. Make sure the TV/projector is on and set to the right input (HDMI 1 / HDMI 2) using its remote.\n"
            "2. Connect the room's HDMI or USB-C cable firmly; with an adapter, try plugging the adapter in before the cable.\n"
            "3. Press Windows Key + P and choose 'Duplicate'.\n"
            "4. Wrong size or cut-off picture: Windows Settings → System → Display → select the room screen → set its recommended resolution.\n"
            "5. No sound through the room screen: click the speaker icon in the taskbar and choose the TV/HDMI output.\n"
            "6. Wireless presenting: use 'Cast' (Windows Key + K) or share the screen from the Teams Room panel.\n"
            "If the room's equipment is faulty, report it with the room name so Facilities/IT can fix it."
        ),
        "tags": "projector meeting room tv screen no signal present presenting presentation hdmi conference room display screen mirroring cast",
    },
    {
        "title": "Company Email Not Working on Phone",
        "category": "software",
        "body": (
            "If work email, Teams or calendar stops syncing on your mobile phone:\n"
            "1. Use the Microsoft Outlook app (not the phone's built-in Mail app) — company policy may block other apps.\n"
            "2. Open the Outlook app → your profile picture → Settings → select your account → Reset Account.\n"
            "3. Make sure the Microsoft Authenticator and Intune Company Portal apps are installed and signed in — they're required for work data on phones.\n"
            "4. Check the phone has internet and its date and time are set automatically.\n"
            "5. If you recently changed your password, remove and re-add the account in Outlook to sign in with the new one.\n"
            "6. New phone: install Company Portal first, enroll the phone, then sign in to Outlook.\n"
            "If the phone shows 'device not compliant', contact IT."
        ),
        "tags": "phone mobile iphone android email on phone outlook app mobile email not syncing company portal intune enroll new phone",
    },

    # ── Windows & software ────────────────────────────────────────────
    {
        "title": "Windows Update Stuck or Failing",
        "category": "software",
        "body": (
            "If updates fail with an error, keep asking to restart, or the PC is stuck on 'Working on updates':\n"
            "1. Stuck on 'Working on updates' / 'Don't turn off your computer': wait at least an hour while plugged in. If nothing has changed for over 2 hours, hold the power button for 10 seconds and start it again.\n"
            "2. Restart the PC normally (Start → Power → Update and restart) — many updates need two restarts.\n"
            "3. Make sure you have at least 20 GB of free disk space (see the low disk space article).\n"
            "4. Run the fixer: Windows Settings → System → Troubleshoot → Other troubleshooters → Windows Update → Run.\n"
            "5. Try again: Windows Settings → Windows Update → Check for updates. Stay connected to the office network or VPN.\n"
            "If the same update keeps failing, contact IT with the error code shown (for example 0x80070002)."
        ),
        "tags": "windows update updates stuck updating update failed update error working on updates dont turn off restart required pending restart 0x80070002",
    },
    {
        "title": "Low Disk Space / Storage Full",
        "category": "software",
        "body": (
            "If Windows says 'Low disk space' or the C: drive is full or red:\n"
            "1. Empty the Recycle Bin.\n"
            "2. Turn on Storage Sense: Windows Settings → System → Storage → Storage Sense → ON → 'Run Storage Sense now'.\n"
            "3. Clean temporary files: Settings → System → Storage → Temporary files → tick everything except Downloads → Remove files.\n"
            "4. Check Downloads: move files you need to OneDrive and delete the rest.\n"
            "5. Free up OneDrive space: right-click the OneDrive folder → 'Free up space' (files stay online and download when opened).\n"
            "6. Uninstall apps you no longer use: Settings → Apps → Installed apps.\n"
            "If the disk is still almost full, contact IT — don't delete files in C:\\Windows or Program Files."
        ),
        "tags": "disk space low disk space storage full c drive full hard drive full out of space no space free up space storage",
    },
    {
        "title": "Microsoft Office Apps (Excel, Word, PowerPoint) Crashing or Not Responding",
        "category": "software",
        "body": (
            "If Excel, Word or PowerPoint freezes, shows 'Not responding', or closes on its own:\n"
            "1. Save your work, then close the app completely and reopen it. If it's frozen, open Task Manager (Ctrl+Shift+Esc) → select the app → End task.\n"
            "2. Start it in Safe Mode to test add-ins: press Windows Key + R, type 'excel /safe' (or 'winword /safe', 'powerpnt /safe') and press Enter.\n"
            "3. If Safe Mode works, turn off add-ins: File → Options → Add-ins → Manage: COM Add-ins → Go → untick them, and re-enable one at a time.\n"
            "4. Update Office: open any Office app → File → Account → Update Options → Update Now.\n"
            "5. Repair Office: Windows Settings → Apps → Installed apps → Microsoft 365 → ⋯ → Modify → Quick Repair (then Online Repair if needed).\n"
            "6. Crashes with one file only: open a copy from OneDrive version history, or recover an unsaved copy via File → Info → Manage Document → Recover Unsaved.\n"
            "If it still crashes after a repair, contact IT."
        ),
        "tags": "excel word powerpoint office crashing crash not responding freezes keeps closing office app hangs spreadsheet document safe mode add-ins",
    },
    {
        "title": "Microsoft Office Says Unlicensed or Asks to Activate",
        "category": "software",
        "body": (
            "If Office shows 'Unlicensed Product', 'Product Deactivated' or keeps asking you to sign in:\n"
            "1. Open Word or Excel → File → Account and make sure you are signed in with your work account (name@company.com), not a personal Microsoft account.\n"
            "2. Sign out of every account there, close all Office apps, reopen and sign in with your work account.\n"
            "3. Make sure you are online — Office needs to check the licence at least every 30 days.\n"
            "4. Clear old sign-ins: Control Panel → Credential Manager → Windows Credentials → remove entries starting with 'MicrosoftOffice'.\n"
            "5. Repair Office: Windows Settings → Apps → Installed apps → Microsoft 365 → Modify → Online Repair.\n"
            "If it still says unlicensed, contact IT — your account may need a licence assigned."
        ),
        "tags": "office license licence unlicensed product activate activation product deactivated subscription expired microsoft 365 sign in to office",
    },
    {
        "title": "Recover a Deleted or Overwritten File",
        "category": "software",
        "body": (
            "If you deleted a file by mistake or saved over it:\n"
            "1. Check the Recycle Bin on your desktop → right-click the file → Restore.\n"
            "2. OneDrive / SharePoint files: open onedrive.com (or the SharePoint site) → Recycle bin → select the file → Restore. Deleted files are kept for 93 days.\n"
            "3. Restore an older version: in OneDrive or SharePoint right-click the file → Version history → Restore the version you want.\n"
            "4. Unsaved Office documents: open the app → File → Info → Manage Document → Recover Unsaved Documents.\n"
            "5. Files on a shared network drive: right-click the folder → Properties → Previous Versions → pick a date → Restore (if available).\n"
            "If you can't find it, contact IT quickly with the file name, location and the date it was last fine — backups can only go back a limited time."
        ),
        "tags": "deleted file recover restore file accidentally deleted lost file overwritten saved over previous version version history recycle bin missing file undo delete",
    },
    {
        "title": "OneDrive Not Syncing",
        "category": "software",
        "body": (
            "If the OneDrive icon shows a red X, 'sync pending' or files aren't updating:\n"
            "1. Click the OneDrive cloud icon in the taskbar to see the error message.\n"
            "2. Make sure you are signed in with your work account and connected to the internet.\n"
            "3. Pause and resume: OneDrive icon → Settings (gear) → Pause syncing → 2 hours, then Resume syncing.\n"
            "4. Check for blocked files: file names can't contain characters like \" * : < > ? / \\ |, and very long folder paths fail — rename or move them.\n"
            "5. Check your storage: OneDrive icon → Settings → Account shows how much space is left.\n"
            "6. Restart OneDrive: OneDrive icon → Settings → Quit OneDrive, then open OneDrive from the Start menu.\n"
            "7. Last resort: press Windows Key + R, type 'onedrive /reset' and press Enter (your files are not deleted).\n"
            "If it still won't sync, contact IT with a screenshot of the error."
        ),
        "tags": "onedrive one drive sync syncing not syncing sync pending red x cloud icon files not updating sync error onedrive stuck",
    },
    {
        "title": "Web Browser Problems: Pages Not Loading, Slow or Pop-ups",
        "category": "software",
        "body": (
            "If Chrome or Edge won't load a site, is very slow, or shows strange pop-ups:\n"
            "1. Check whether other websites load. If none do, see the Wi-Fi / network articles.\n"
            "2. Reload without cache: press Ctrl+F5 on the page.\n"
            "3. Clear browsing data: press Ctrl+Shift+Delete → Time range 'All time' → tick 'Cached images and files' and 'Cookies' → Clear data.\n"
            "4. Try an InPrivate / Incognito window (Ctrl+Shift+N) — if the site works there, an extension is the cause: open Extensions and turn them off one at a time.\n"
            "5. Update the browser: Edge → Settings → About Microsoft Edge; Chrome → Settings → About Chrome. Restart it afterwards.\n"
            "6. Company sites: make sure you are on the office network or VPN.\n"
            "7. Pop-ups asking you to call a number or 'your PC is infected' are scams — close the browser, don't call or click, and report it to IT."
        ),
        "tags": "browser chrome edge firefox website not loading page not loading site down web page slow browser pop ups popups cache cookies extension internet explorer",
    },
    {
        "title": "Website Security Warning: 'Your connection is not private'",
        "category": "network",
        "body": (
            "If a site shows 'Your connection is not private', 'NET::ERR_CERT' or a certificate warning:\n"
            "1. Check your PC's date and time are correct: Windows Settings → Time & Language → Date & time → turn on 'Set time automatically' and click 'Sync now'.\n"
            "2. Check the web address is spelled correctly and starts with https://.\n"
            "3. Hotel, airport or café Wi-Fi: open any normal site first to get the Wi-Fi sign-in page, then try again.\n"
            "4. Clear the browser cache (Ctrl+Shift+Delete) and restart the browser.\n"
            "5. Do NOT click 'Proceed anyway' or enter a password on a site with this warning.\n"
            "If an internal company site shows the warning for everyone, report it to IT — the site's certificate may have expired."
        ),
        "tags": "certificate error ssl connection is not private not secure security warning net err cert expired certificate https warning website warning",
    },
    {
        "title": "How to Install Software (Company Portal / Software Center)",
        "category": "software",
        "body": (
            "To install an approved app such as Adobe Reader, Zoom, Chrome or Visio:\n"
            "1. Open Start → search 'Company Portal' (or 'Software Center' on older PCs).\n"
            "2. Search for the app → click Install. It installs automatically, no admin password needed.\n"
            "3. Restart the PC if Company Portal asks you to.\n"
            "4. If an install fails, click Retry, make sure you're on the office network or VPN, and restart.\n"
            "5. Apps not listed in Company Portal need approval: raise a software request ticket with the app name, why you need it, and your manager's approval.\n"
            "Don't download installers from the internet — they're blocked and may contain malware."
        ),
        "tags": "install software install app installation company portal software center download program application request admin rights need software new software",
    },
    {
        "title": "An Application Won't Open or Keeps Closing",
        "category": "software",
        "body": (
            "If a program does nothing when you open it, shows an error, or closes straight away:\n"
            "1. Check it isn't already running hidden: press Ctrl+Shift+Esc → Task Manager → find the app → End task, then open it again.\n"
            "2. Restart the PC — this fixes most apps that won't start.\n"
            "3. Run updates: Windows Settings → Windows Update, and update the app from Company Portal.\n"
            "4. Repair or reset it: Windows Settings → Apps → Installed apps → the app → ⋯ → Advanced options / Modify → Repair (then Reset if needed).\n"
            "5. Reinstall it from Company Portal.\n"
            "6. Write down the exact error message or take a screenshot (Windows Key + Shift + S).\n"
            "If it still won't open, contact IT with the app name and the error."
        ),
        "tags": "app wont open application not opening program wont start software keeps closing app closes immediately error opening app not launching",
    },
    {
        "title": "Microsoft Teams Not Loading, Signing In or Showing Messages",
        "category": "software",
        "body": (
            "If Teams shows a white or blank screen, loops at sign-in, or chats and messages don't appear:\n"
            "1. Quit Teams fully: right-click the Teams icon in the taskbar tray → Quit, then reopen it.\n"
            "2. Try Teams in your browser at teams.microsoft.com — if it works there, the desktop app needs a reset.\n"
            "3. Clear the Teams cache: quit Teams → Windows Settings → Apps → Installed apps → Microsoft Teams → Advanced options → Reset.\n"
            "4. Sign out and back in: click your profile picture → Sign out, then sign in with your work account.\n"
            "5. Update Teams: profile picture / ⋯ → Settings → About Teams (updates install automatically), then restart it.\n"
            "6. Make sure the PC's date and time are correct and you have internet.\n"
            "If Teams is down for everyone, check the Service Desk outage banner."
        ),
        "tags": "teams microsoft teams not loading white screen blank screen sign in loop cant sign in teams messages not showing chat not loading teams wont open teams stuck",
    },
    {
        "title": "Screen Sharing Not Working in Teams or Zoom",
        "category": "software",
        "body": (
            "If others see a black screen when you share, or the Share button is greyed out:\n"
            "1. Share a single window instead of the whole screen (Teams: Share → Window), or the reverse.\n"
            "2. Close and reopen the app you're trying to share, then share again.\n"
            "3. Videos or protected content (DRM) show as black — share the browser tab with 'Share tab audio' instead, or ask others to open the link.\n"
            "4. Disable hardware acceleration if you see a black share in Teams: Settings → General → tick 'Disable GPU hardware acceleration' and restart Teams.\n"
            "5. Greyed-out Share button: the meeting organiser may have limited presenting — ask them to make you a Presenter.\n"
            "6. Update Teams/Zoom and restart the PC.\n"
            "If it still fails in every meeting, contact IT."
        ),
        "tags": "screen sharing share screen screenshare cant share screen sharing black screen share button greyed out present screen teams share zoom share",
    },
    {
        "title": "Outlook Search Not Finding Emails",
        "category": "software",
        "body": (
            "If Outlook search returns no results or misses emails you know exist:\n"
            "1. Check the search scope at the top: change 'Current Folder' to 'All Mailboxes' / 'All Outlook Items'.\n"
            "2. Restart Outlook and wait a few minutes — indexing may still be catching up.\n"
            "3. Check indexing status: click in the search box → Search tab → Search Tools → Indexing Status.\n"
            "4. Rebuild the index: Windows Settings → search 'Indexing Options' → Advanced → Rebuild (this can take a few hours; keep the PC on).\n"
            "5. Try searching in Outlook on the web (outlook.office.com) — it searches the whole mailbox on the server.\n"
            "If search still fails, contact IT."
        ),
        "tags": "outlook search not working search not finding emails cant find email search results indexing outlook search empty",
    },
    {
        "title": "Outlook Can't Send Email or Messages Stuck in Outbox",
        "category": "software",
        "body": (
            "If emails stay in the Outbox, bounce back, or won't send:\n"
            "1. Check the bottom of Outlook says 'Connected'. If it says 'Working offline', go to Send / Receive → turn off 'Work Offline'.\n"
            "2. Large attachments: messages over about 20–25 MB are rejected. Share big files as a OneDrive link instead (Attach → Share link).\n"
            "3. Open the stuck message in the Outbox, then click Send again — or delete it and send a new copy.\n"
            "4. Bounce-back (NDR) message: read it — 'recipient not found' means the address is wrong; 'mailbox full' means yours or theirs is full.\n"
            "5. Mailbox full: empty Deleted Items and archive or delete old emails with big attachments.\n"
            "6. Restart Outlook and try sending from Outlook on the web (outlook.office.com) to see whether it's the app or the account.\n"
            "If nothing sends, even from the web, contact IT."
        ),
        "tags": "email not sending cant send email stuck in outbox outbox outlook send error bounce back undeliverable ndr attachment too large mailbox full work offline",
    },
    {
        "title": "Outlook Calendar, Meeting Invites and Shared Mailboxes",
        "category": "software",
        "body": (
            "If meetings are missing, invites aren't arriving, or a shared mailbox or calendar doesn't show:\n"
            "1. Calendar not updating: click Send / Receive → Update Folder, then restart Outlook.\n"
            "2. Check the same calendar in Outlook on the web (outlook.office.com) — if it's right there, the desktop app is out of sync.\n"
            "3. Missing invites: check the Deleted Items and Junk Email folders and any Inbox rules (File → Manage Rules & Alerts).\n"
            "4. Wrong meeting times: Windows Settings → Time & Language → Date & time → set the correct time zone; then Outlook → File → Options → Calendar → Time zones.\n"
            "5. Shared mailbox not showing: shared mailboxes appear automatically about an hour after access is granted — restart Outlook. To add one manually: File → Account Settings → Account Settings → Change → More Settings → Advanced → Add.\n"
            "6. Open a colleague's calendar: Calendar → Add Calendar → From Address Book.\n"
            "If you need access to a shared mailbox, ask its owner or raise an access request."
        ),
        "tags": "calendar meeting invite meeting request invites missing shared mailbox shared calendar appointment meetings not showing time zone outlook calendar",
    },
    {
        "title": "Set Up Email Signature or Out-of-Office Reply",
        "category": "software",
        "body": (
            "To set your email signature or automatic replies:\n"
            "1. Signature in Outlook (desktop): File → Options → Mail → Signatures → New, type it, and choose it for 'New messages' and 'Replies/forwards'.\n"
            "2. Signature in Outlook on the web / new Outlook: Settings (gear) → Mail / Accounts → Signatures.\n"
            "3. Out of office: File → Automatic Replies (Out of Office) → 'Send automatic replies' → set the dates and write messages for inside and outside the company.\n"
            "4. On the web / new Outlook: Settings → Mail / Accounts → Automatic replies.\n"
            "5. On your phone: Outlook app → Settings → your account → Automatic replies.\n"
            "Remember to turn automatic replies off when you return, or set an end date."
        ),
        "tags": "signature email signature out of office automatic reply auto reply autoreply vacation reply away message holiday ooo",
    },
    {
        "title": "Spam or Junk Email",
        "category": "software",
        "body": (
            "If you get lots of unwanted email, or real emails go to Junk:\n"
            "1. Unwanted email: select it → Report → Report junk (or Block → Block sender).\n"
            "2. Real emails in Junk: open the Junk Email folder → select the email → Report → Not junk. Add the sender to Safe Senders: Home → Junk → Junk E-mail Options → Safe Senders.\n"
            "3. Don't click 'Unsubscribe' in emails you never signed up for — it confirms your address to spammers.\n"
            "4. Check Inbox rules aren't moving mail: File → Manage Rules & Alerts.\n"
            "If an email asks for your password, payment or urgent action, don't click anything — use Report → Report phishing and tell IT security."
        ),
        "tags": "spam junk junk mail spam email unwanted email too many emails emails going to junk safe senders block sender newsletter",
    },
    {
        "title": "PDF Files Won't Open or Print",
        "category": "software",
        "body": (
            "If PDF files won't open, open in the wrong app, or print incorrectly:\n"
            "1. Set the default app: right-click a PDF → Open with → Choose another app → pick Adobe Acrobat Reader or Microsoft Edge → tick 'Always use this app'.\n"
            "2. Adobe Reader not installed: install it from Company Portal.\n"
            "3. Downloaded PDF won't open: download it again — the first copy may be incomplete — or open it in Microsoft Edge.\n"
            "4. Adobe shows errors: Help → Repair Installation, or turn off 'Enable Protected Mode at startup' only if IT advises.\n"
            "5. PDF prints wrongly: in the print window click Advanced → tick 'Print as image'.\n"
            "6. Password-protected PDF: you need the password from the person who sent it.\n"
            "If a PDF from outside the company looks suspicious, don't open it — report it to IT."
        ),
        "tags": "pdf pdf wont open adobe acrobat reader cant open pdf pdf error pdf not opening pdf print default app",
    },
    {
        "title": "Copy and Paste Not Working",
        "category": "software",
        "body": (
            "If Ctrl+C / Ctrl+V or right-click Copy/Paste stops working:\n"
            "1. Try the right-click menu instead of the keyboard (or the reverse) to see which part is failing.\n"
            "2. Press Ctrl+C a few times firmly; check the Ctrl key works in other shortcuts like Ctrl+A.\n"
            "3. Restart the app you're copying from and the one you're pasting into.\n"
            "4. Restart Windows Explorer: Ctrl+Shift+Esc → Task Manager → find 'Windows Explorer' → Restart.\n"
            "5. Clipboard history: press Windows Key + V. If it's off, turn it on and pick the item you copied.\n"
            "6. Remote Desktop: copy/paste between PCs needs 'Clipboard' ticked in the Remote Desktop Local Resources settings.\n"
            "7. Restart the PC.\n"
            "Some company apps and documents block copying on purpose for security."
        ),
        "tags": "copy paste copy and paste ctrl c ctrl v clipboard cant paste paste not working copy not working cut",
    },
    {
        "title": "Wrong Date, Time or Time Zone",
        "category": "software",
        "body": (
            "If the computer clock is wrong, or meeting times are off by hours:\n"
            "1. Windows Settings → Time & Language → Date & time.\n"
            "2. Turn on 'Set time automatically' and 'Set time zone automatically', then click 'Sync now'.\n"
            "3. If the time zone is still wrong, turn off 'Set time zone automatically' and choose your time zone from the list.\n"
            "4. Restart Outlook and Teams so meeting times refresh.\n"
            "5. If the clock resets after every shutdown, the PC's internal battery may be failing — contact IT.\n"
            "A wrong clock can also cause sign-in, MFA and website certificate errors."
        ),
        "tags": "time wrong date wrong clock wrong time zone timezone clock incorrect meeting time wrong daylight saving",
    },
    {
        "title": "Remote Desktop (RDP) Won't Connect",
        "category": "network",
        "body": (
            "If Remote Desktop says it can't connect to the remote computer:\n"
            "1. When working from home, connect to the company VPN first.\n"
            "2. Check the computer name is spelled correctly (for example CORP-PC-1234) — try the full name with '.corp.internal' on the end.\n"
            "3. Make sure the remote PC is switched on and not asleep — ask a colleague in the office to check, or turn on 'Wake on LAN' with IT.\n"
            "4. Use your work username in the form CORP\\username or name@company.com.\n"
            "5. 'Your credentials did not work': type your password carefully and check Caps Lock; a recently changed password may need a restart of the remote PC.\n"
            "6. Only one person can use a remote PC at a time — someone else may be signed in.\n"
            "If you still can't connect, contact IT with the computer name and the exact error."
        ),
        "tags": "remote desktop rdp remote connection mstsc cant connect remote pc remote computer remote access work computer from home terminal server",
    },
    {
        "title": "Can't Sign In to Windows (PIN, Fingerprint or Trust Relationship Error)",
        "category": "access",
        "body": (
            "If you can't log in to your work computer:\n"
            "1. PIN or fingerprint not working: click 'Sign-in options' under the PIN box and choose the password (key) icon, then sign in with your password.\n"
            "2. Reset a forgotten PIN: click 'I forgot my PIN' on the sign-in screen and follow the prompts (needs internet).\n"
            "3. 'The trust relationship between this workstation and the primary domain failed': unplug from the network, sign in, reconnect and restart. If it persists, IT must re-join the PC to the domain.\n"
            "4. 'Other user' screen: type your username as CORP\\username or name@company.com.\n"
            "5. Password just changed at home: connect to the office network or VPN so the laptop learns the new password, or sign in once with the old one.\n"
            "6. Account locked: wait 15 minutes or reset your password at the self-service portal.\n"
            "If you're still locked out, call the Service Desk."
        ),
        "tags": "windows login cant log in sign in pin fingerprint windows hello face recognition trust relationship domain login screen user profile cant login to computer logon",
    },
    {
        "title": "BitLocker Recovery Key Screen",
        "category": "access",
        "body": (
            "If your laptop starts with a blue 'BitLocker recovery' screen asking for a 48-digit key:\n"
            "1. Don't keep restarting or try random keys.\n"
            "2. On your phone or another computer, go to https://myaccount.microsoft.com → Devices → your laptop → 'View BitLocker Keys'.\n"
            "3. Match the 'Key ID' shown on the blue screen with the one on the website, and type the 48-digit recovery key.\n"
            "4. If no key is listed, contact the Service Desk with the Key ID shown on screen — IT can look it up after verifying your identity.\n"
            "5. After it starts, restart once normally. This screen often appears after a BIOS update, a docking change or a hardware repair.\n"
            "Never share your recovery key with anyone who contacts you unexpectedly."
        ),
        "tags": "bitlocker recovery key bitlocker key 48 digit key blue screen recovery key encryption locked drive bitlocker recovery",
    },

    # ── Network ───────────────────────────────────────────────────────
    {
        "title": "Wired (Ethernet) Network Not Working",
        "category": "network",
        "body": (
            "If your PC is plugged in with a network cable but shows no internet or 'Unidentified network':\n"
            "1. Check the cable clicks in firmly at both ends — the port light next to the cable should be on or blinking.\n"
            "2. Try another cable or another wall/desk port.\n"
            "3. Using a dock or USB adapter: plug the cable directly into the laptop if possible, or reconnect the dock.\n"
            "4. Reset the adapter: press Windows Key + R, type 'ncpa.cpl' → right-click 'Ethernet' → Disable → wait 10 seconds → Enable.\n"
            "5. Renew your address: open Command Prompt and run 'ipconfig /release' then 'ipconfig /renew'.\n"
            "6. Turn off Wi-Fi briefly to test the wired connection on its own.\n"
            "If the port light stays off with a good cable, the desk port may be disabled — contact IT with your desk number."
        ),
        "tags": "ethernet wired network lan cable network cable unidentified network no internet plugged in network port wired connection",
    },
    {
        "title": "Slow Internet Connection",
        "category": "network",
        "body": (
            "If web pages, Teams calls or downloads are slow:\n"
            "1. Test your speed at speedtest.net (or fast.com) and note the result.\n"
            "2. Wi-Fi: move closer to the access point or router, or use a network cable.\n"
            "3. At home: restart your router (unplug it for 30 seconds) and pause big downloads, streaming or game updates on other devices.\n"
            "4. On VPN: disconnect and reconnect, or choose a closer VPN gateway — VPN adds some delay.\n"
            "5. Close apps that sync a lot (OneDrive uploads, Windows updates) or pause OneDrive syncing for 2 hours.\n"
            "6. Restart your PC.\n"
            "If the whole office is slow, report it so IT can check for an outage."
        ),
        "tags": "slow internet internet slow slow connection slow network bandwidth buffering lag speed internet speed slow download slow wifi",
    },

    # ── Security (guidance; the chatbot also escalates these to a person) ─
    {
        "title": "Virus, Malware or Suspicious Pop-ups",
        "category": "access",
        "body": (
            "If you see warnings that your PC is infected, unexpected pop-ups, new toolbars or programs you didn't install:\n"
            "1. Don't click the pop-up, call any phone number it shows, or pay anything — these are scams.\n"
            "2. Disconnect from the network: turn off Wi-Fi or unplug the network cable.\n"
            "3. Contact the Service Desk / IT security immediately and describe what you saw (a photo of the screen helps).\n"
            "4. If you typed your password anywhere suspicious, change it from a different, trusted device.\n"
            "5. Don't try to remove it yourself and don't keep working on the PC until IT has checked it.\n"
            "Company PCs run managed antivirus; IT will scan and clean the device."
        ),
        "tags": "virus malware infected pop ups popup scam ransomware antivirus trojan spyware your pc is infected suspicious program hacked",
    },
]


def sync_kb_library(db, models, overwrite: bool = False) -> int:
    """Add library articles missing from the database (matched by title).
    With overwrite=True, also refresh the text of ones that exist (seed.py).
    Returns the number of articles added."""
    added = 0
    for article in KB_LIBRARY:
        existing = db.query(models.KBArticle).filter_by(title=article["title"]).first()
        if not existing:
            db.add(models.KBArticle(status="published", source="manual", **article))
            added += 1
        elif overwrite:
            existing.body = article["body"]
            existing.tags = article["tags"]
            existing.category = article["category"]
    db.commit()
    return added
