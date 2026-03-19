import SwiftUI

struct ContentView: View {
    @EnvironmentObject var api: BarryAPI
    @EnvironmentObject var appState: AppState

    var body: some View {
        ZStack(alignment: .bottom) {
            Group {
                switch appState.selectedTab {
                case 0: HomeView()
                case 1: ChatView()
                case 2: CalendarView()
                default: HomeView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            BarryTabBar()
        }
        .ignoresSafeArea(edges: .bottom)
        .sheet(isPresented: $appState.showAddTodo) {
            AddTodoSheet(isPresented: $appState.showAddTodo, onAdd: { title, priority in
                Task { try? await api.addTodo(title: title, priority: priority) }
            })
        }
    }
}

// MARK: - Custom Tab Bar
struct BarryTabBar: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        HStack(spacing: 16) {
            // Chat
            TabCircleButton(
                icon: "bubble.left.fill",
                selected: appState.selectedTab == 1
            ) { appState.selectedTab = 1 }

            // Tasks pill (center)
            HStack(spacing: 0) {
                Button {
                    appState.selectedTab = 0
                } label: {
                    HStack(spacing: 7) {
                        Image(systemName: "calendar")
                            .font(.system(size: 14, weight: .semibold))
                        Text("Tasks")
                            .font(.system(size: 15, weight: .semibold))
                    }
                    .foregroundColor(.white)
                    .padding(.leading, 18)
                    .padding(.trailing, 12)
                    .padding(.vertical, 15)
                }

                Rectangle()
                    .fill(Color.white.opacity(0.25))
                    .frame(width: 1, height: 22)

                Button {
                    appState.showAddTodo = true
                } label: {
                    Image(systemName: "plus")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.white)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 15)
                }
            }
            .background(Color.black)
            .clipShape(Capsule())

            // Calendar/Stats
            TabCircleButton(
                icon: "chart.bar.fill",
                selected: appState.selectedTab == 2
            ) { appState.selectedTab = 2 }
        }
        .padding(.horizontal, 28)
        .padding(.bottom, 34)
        .padding(.top, 12)
        .background(
            Rectangle()
                .fill(.ultraThinMaterial)
                .ignoresSafeArea()
                .opacity(0)
        )
    }
}

struct TabCircleButton: View {
    let icon: String
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            ZStack {
                Circle()
                    .fill(selected ? Color.black : Color(.systemGray5))
                    .frame(width: 48, height: 48)
                Image(systemName: icon)
                    .font(.system(size: 16, weight: .medium))
                    .foregroundColor(selected ? .white : Color(.label))
            }
        }
    }
}
