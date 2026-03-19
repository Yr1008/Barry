import SwiftUI

@main
struct BarryApp: App {
    @StateObject private var api = BarryAPI()
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(api)
                .environmentObject(appState)
                .preferredColorScheme(.light)
        }
    }
}

class AppState: ObservableObject {
    @Published var selectedTab = 0
    @Published var showAddTodo = false
}
