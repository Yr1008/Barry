import SwiftUI

struct StatusView: View {
    @EnvironmentObject var api: BarryAPI

    var body: some View {
        NavigationView {
            List {
                Section("Connection") {
                    HStack {
                        Circle()
                            .fill(api.isOnline ? Color.green : Color.red)
                            .frame(width: 9, height: 9)
                        Text(api.isOnline ? "Connected" : "Offline")
                        Spacer()
                        Text(api.baseURL).font(.caption).foregroundColor(.secondary)
                    }
                }

                if let s = api.status {
                    Section("Memory") {
                        infoRow("Todos", "\(s.memory.todos)")
                        infoRow("Facts", "\(s.memory.facts)")
                        infoRow("Tone profiles", "\(s.memory.toneProfiles)")
                        infoRow("Conversation", "\(s.memory.conversationHistory) msgs")
                    }
                    Section("Connectors") {
                        connectorRow("Google Calendar", active: s.connectors.googleCalendar)
                        connectorRow("iCloud", active: s.connectors.icloud)
                        connectorRow("Email", active: s.connectors.email)
                        connectorRow("WhatsApp", active: s.connectors.whatsapp)
                        connectorRow("iPhone Shortcuts", active: s.connectors.iphoneShortcuts)
                    }
                }
            }
            .navigationTitle("Status")
            .refreshable { await api.refreshStatus() }
        }
    }

    private func infoRow(_ label: String, _ value: String) -> some View {
        HStack { Text(label).foregroundColor(.secondary); Spacer(); Text(value) }
    }

    private func connectorRow(_ name: String, active: Bool) -> some View {
        HStack {
            Text(name)
            Spacer()
            Text(active ? "on" : "off")
                .font(.system(size: 12, weight: .semibold))
                .padding(.horizontal, 10).padding(.vertical, 3)
                .background(active ? Color.green.opacity(0.12) : Color.red.opacity(0.1))
                .foregroundColor(active ? .green : .red)
                .cornerRadius(8)
        }
    }
}
