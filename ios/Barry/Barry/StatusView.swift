import SwiftUI

struct StatusView: View {
    @EnvironmentObject var api: BarryAPI
    @State private var isRefreshing = false

    var body: some View {
        NavigationView {
            ZStack {
                Color(hex: "0a0a0f").ignoresSafeArea()
                ScrollView {
                    VStack(spacing: 16) {
                        // Connection card
                        StatusCard(title: "Connection") {
                            HStack {
                                Circle()
                                    .fill(api.isOnline ? Color.green : Color.red)
                                    .frame(width: 10, height: 10)
                                    .shadow(color: api.isOnline ? .green : .red, radius: 4)
                                Text(api.isOnline ? "Connected to Barry" : "Barry is offline")
                                    .font(.system(size: 15))
                                Spacer()
                                Text(api.baseURL)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }

                        if let s = api.status {
                            // Memory card
                            StatusCard(title: "Memory") {
                                VStack(spacing: 10) {
                                    StatRow(label: "Pending todos", value: "\(s.memory.todos)", color: .yellow)
                                    StatRow(label: "Facts learned", value: "\(s.memory.facts)", color: .green)
                                    StatRow(label: "Tone profiles", value: "\(s.memory.toneProfiles)", color: Color(hex: "a78bfa"))
                                    StatRow(label: "Conversation history", value: "\(s.memory.conversationHistory)", color: .blue)
                                }
                            }

                            // Connectors card
                            StatusCard(title: "Connectors") {
                                VStack(spacing: 10) {
                                    ConnectorRow(name: "Google Calendar", icon: "📅", active: s.connectors.googleCalendar)
                                    ConnectorRow(name: "iCloud", icon: "🍎", active: s.connectors.icloud)
                                    ConnectorRow(name: "Email", icon: "📧", active: s.connectors.email)
                                    ConnectorRow(name: "WhatsApp", icon: "💬", active: s.connectors.whatsapp)
                                    ConnectorRow(name: "iPhone Shortcuts", icon: "📱", active: s.connectors.iphoneShortcuts)
                                }
                            }

                            // Info card
                            StatusCard(title: "Info") {
                                VStack(spacing: 10) {
                                    StatRow(label: "Owner", value: s.owner, color: .primary)
                                    StatRow(label: "Timezone", value: s.timezone, color: .secondary)
                                    StatRow(label: "Last synced events", value: "\(s.lastEvents)", color: .primary)
                                    StatRow(label: "Last synced emails", value: "\(s.lastEmails)", color: .primary)
                                }
                            }
                        }

                        Spacer(minLength: 20)
                    }
                    .padding(16)
                }
            }
            .navigationTitle("Status")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: refresh) {
                        Image(systemName: "arrow.clockwise")
                            .rotationEffect(.degrees(isRefreshing ? 360 : 0))
                            .animation(isRefreshing ? .linear(duration: 0.6).repeatForever(autoreverses: false) : .default, value: isRefreshing)
                            .foregroundColor(Color(hex: "a78bfa"))
                    }
                }
            }
        }
        .onAppear(perform: refresh)
    }

    private func refresh() {
        isRefreshing = true
        Task {
            await api.refreshStatus()
            await MainActor.run { isRefreshing = false }
        }
    }
}

struct StatusCard<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title.uppercased())
                .font(.system(size: 11, weight: .semibold))
                .foregroundColor(.secondary)
                .kerning(1)
            content
        }
        .padding(16)
        .background(Color(hex: "111118"))
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Color.white.opacity(0.07)))
    }
}

struct StatRow: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        HStack {
            Text(label).foregroundColor(.secondary).font(.system(size: 14))
            Spacer()
            Text(value).foregroundColor(color).font(.system(size: 14, weight: .semibold))
        }
    }
}

struct ConnectorRow: View {
    let name: String
    let icon: String
    let active: Bool

    var body: some View {
        HStack(spacing: 10) {
            Text(icon).font(.system(size: 15))
            Text(name).font(.system(size: 14)).foregroundColor(.secondary)
            Spacer()
            Text(active ? "on" : "off")
                .font(.system(size: 11, weight: .semibold))
                .padding(.horizontal, 10)
                .padding(.vertical, 3)
                .background(active ? Color.green.opacity(0.15) : Color.red.opacity(0.12))
                .foregroundColor(active ? .green : .red)
                .cornerRadius(10)
                .overlay(RoundedRectangle(cornerRadius: 10)
                    .stroke(active ? Color.green.opacity(0.3) : Color.red.opacity(0.2)))
        }
    }
}
