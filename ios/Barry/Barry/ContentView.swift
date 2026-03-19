import SwiftUI

struct ContentView: View {
    @EnvironmentObject var api: BarryAPI
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            ChatView()
                .tabItem {
                    Label("Chat", systemImage: "bubble.left.and.bubble.right.fill")
                }
                .tag(0)

            BriefingView()
                .tabItem {
                    Label("Briefing", systemImage: "sun.max.fill")
                }
                .tag(1)

            TodosView()
                .tabItem {
                    Label("Todos", systemImage: "checklist")
                }
                .tag(2)

            StatusView()
                .tabItem {
                    Label("Status", systemImage: "antenna.radiowaves.left.and.right")
                }
                .tag(3)

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape.fill")
                }
                .tag(4)
        }
        .tint(Color("AccentPurple"))
    }
}
