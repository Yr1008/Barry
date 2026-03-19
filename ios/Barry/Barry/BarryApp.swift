import SwiftUI

@main
struct BarryApp: App {
    @StateObject private var api = BarryAPI()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(api)
                .preferredColorScheme(.dark)
        }
    }
}
