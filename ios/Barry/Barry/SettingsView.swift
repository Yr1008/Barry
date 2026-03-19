import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var api: BarryAPI
    @State private var urlInput = ""
    @State private var saved = false

    var body: some View {
        NavigationView {
            Form {
                Section {
                    VStack(alignment: .center, spacing: 12) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 20)
                                .fill(Color.black)
                                .frame(width: 70, height: 70)
                            Text("⚡").font(.system(size: 36))
                        }
                        Text("Barry").font(.title2).bold()
                        Text("Personal AI Assistant")
                            .font(.subheadline).foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                }

                Section(header: Text("Server"),
                        footer: Text("URL of your Barry backend server.")) {
                    HStack {
                        TextField("http://your-server:8000", text: $urlInput)
                            .autocapitalization(.none)
                            .autocorrectionDisabled()
                            .keyboardType(.URL)
                        if saved {
                            Image(systemName: "checkmark.circle.fill").foregroundColor(.green)
                        }
                    }
                    Button("Save & Connect") {
                        api.baseURL = urlInput.trimmingCharacters(in: .whitespacesAndNewlines)
                            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
                        saved = true
                        Task { await api.refreshStatus() }
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { saved = false }
                    }
                    .disabled(urlInput.trimmingCharacters(in: .whitespaces).isEmpty)
                }

                Section(header: Text("Quick Setup")) {
                    presetRow("Local Mac", url: "http://localhost:8000", icon: "laptopcomputer")
                    presetRow("Same WiFi", url: "http://192.168.1.100:8000", icon: "wifi")
                }

                Section(header: Text("About")) {
                    infoRow("Version", "1.0.0")
                    infoRow("Model", "Claude Sonnet 4.6")
                    infoRow("Backend", "FastAPI + Python")
                }
            }
            .navigationTitle("Settings")
        }
        .onAppear { urlInput = api.baseURL }
    }

    @ViewBuilder
    private func presetRow(_ label: String, url: String, icon: String) -> some View {
        Button {
            urlInput = url
            api.baseURL = url
            Task { await api.refreshStatus() }
        } label: {
            HStack {
                Image(systemName: icon).frame(width: 20)
                Text(label)
                Spacer()
                Text(url).font(.caption).foregroundColor(.secondary)
            }
            .foregroundColor(.primary)
        }
    }

    private func infoRow(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label).foregroundColor(.secondary)
            Spacer()
            Text(value)
        }
    }
}
