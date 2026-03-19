# Barry iOS App

Native SwiftUI iOS app for Barry — your personal AI assistant.

## Setup

### Option A — XcodeGen (recommended)

```bash
brew install xcodegen
cd ios/Barry
xcodegen generate
open Barry.xcodeproj
```

### Option B — Manual Xcode setup

1. Open Xcode → **File → New → Project**
2. Choose **iOS → App**
3. Set:
   - Product Name: `Barry`
   - Interface: `SwiftUI`
   - Language: `Swift`
   - Minimum Deployments: `iOS 17`
4. **Delete** the generated `ContentView.swift` and `BarryApp.swift`
5. **Drag all `.swift` files** from `ios/Barry/Barry/` into the project
6. Copy `Info.plist` entries (NSAppTransportSecurity) into your project's Info tab

## Configuration

On first launch, go to **Settings tab** and enter your Barry server URL:
- Local Mac: `http://localhost:8000`
- Same WiFi network: `http://YOUR_MAC_IP:8000`

## Features

- **Chat** — streaming chat with Barry, quick prompt chips
- **Briefing** — daily AI-generated briefing
- **Todos** — view, add, and complete todos with priorities
- **Status** — live connector status and memory stats
- **Settings** — configure server URL
