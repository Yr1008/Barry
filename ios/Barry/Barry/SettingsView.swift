import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var api: BarryAPI
    @State private var urlInput = ""
    @State private var saved = false

    var body: some View {
        NavigationView {
            ZStack {
                Color(hex: "0a0a0f").ignoresSafeArea()
                Form {
                    Section {
                        VStack(alignment: .center, spacing: 12) {
                            ZStack {
                                RoundedRectangle(cornerRadius: 18)
                                    .fill(LinearGradient(
                                        colors: [Color(hex: "7c6aff"), Color(hex: "a78bfa")],
                                        startPoint: .topLeading, endPoint: .bottomTrailing))
                                    .frame(width: 70, height: 70)
                                Text("⚡").font(.system(size: 35))
                            }
                            Text("Barry").font(.title2).bold()
                            Text("Personal AI Assistant").font(.subheadline).foregroundColor(.secondary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                    }
                    .listRowBackground(Color(hex: "111118"))

                    Section(header: Text("Server"), footer: Text("The URL of your Barry backend server.")) {
                        HStack {
                            TextField("http://your-server:8000", text: $urlInput)
                                .autocapitalization(.none)
                                .autocorrectionDisabled()
                                .keyboardType(.URL)
                            if saved {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundColor(.green)
                            }
                        }
                        Button("Save & Connect") {
                            let url = urlInput.trimmingCharacters(in: .whitespaces)
                                .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
                            api.baseURL = url
                            saved = true
                            Task { await api.refreshStatus() }
                            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { saved = false }
                        }
                        .foregroundColor(Color(hex: "a78bfa"))
                        .disabled(urlInput.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                    .listRowBackground(Color(hex: "111118"))

                    Section(header: Text("Quick Setup")) {
                        serverPreset(label: "Local Mac", url: "http://localhost:8000", icon: "laptopcomputer")
                        serverPreset(label: "Local Network", url: "http://192.168.1.100:8000", icon: "wifi")
                    }
                    .listRowBackground(Color(hex: "111118"))

                    Section(header: Text("About")) {
                        InfoRow(label: "Version", value: "1.0.0")
                        InfoRow(label: "Model", value: "Claude Sonnet 4.6")
                        InfoRow(label: "Backend", value: "FastAPI + Python")
                        Link(destination: URL(string: "https://github.com/Yr1008/Barry")!) {
                            HStack {
                                Image(systemName: "chevron.left.forwardslash.chevron.right")
                                    .foregroundColor(Color(hex: "a78bfa"))
                                Text("GitHub Repository")
                                    .foregroundColor(Color(hex: "a78bfa"))
                            }
                        }
                    }
                    .listRowBackground(Color(hex: "111118"))
                }
                .scrollContentBackground(.hidden)
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
        }
        .onAppear { urlInput = api.baseURL }
    }

    @ViewBuilder
    private func serverPreset(label: String, url: String, icon: String) -> some View {
        Button(action: {
            urlInput = url
            api.baseURL = url
            Task { await api.refreshStatus() }
        }) {
            HStack {
                Image(systemName: icon).foregroundColor(Color(hex: "a78bfa")).frame(width: 20)
                Text(label)
                Spacer()
                Text(url).font(.caption).foregroundColor(.secondary)
                Image(systemName: "arrow.right.circle").foregroundColor(Color(hex: "7c6aff").opacity(0.6))
            }
        }
        .foregroundColor(.primary)
    }
}

struct InfoRow: View {
    let label: String
    let value: String
    var body: some View {
        HStack {
            Text(label).foregroundColor(.secondary)
            Spacer()
            Text(value).foregroundColor(.primary)
        }
    }
}
