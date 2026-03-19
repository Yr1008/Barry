import SwiftUI

struct BriefingView: View {
    @EnvironmentObject var api: BarryAPI
    @State private var briefing: String = ""
    @State private var isLoading = false
    @State private var lastGenerated: Date?

    var body: some View {
        NavigationView {
            ZStack {
                Color(hex: "0a0a0f").ignoresSafeArea()

                if briefing.isEmpty && !isLoading {
                    VStack(spacing: 20) {
                        Image(systemName: "sun.max.fill")
                            .font(.system(size: 60))
                            .foregroundStyle(LinearGradient(
                                colors: [.yellow, .orange],
                                startPoint: .top, endPoint: .bottom))
                        Text("Your daily briefing")
                            .font(.title2).bold()
                        Text("Get a summary of your day, priorities, and what needs your attention.")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 40)
                        Button(action: generate) {
                            Label("Generate Briefing", systemImage: "bolt.fill")
                                .font(.headline)
                                .foregroundColor(.white)
                                .padding(.horizontal, 28)
                                .padding(.vertical, 14)
                                .background(LinearGradient(
                                    colors: [Color(hex: "7c6aff"), Color(hex: "6355e8")],
                                    startPoint: .leading, endPoint: .trailing))
                                .cornerRadius(14)
                                .shadow(color: Color(hex: "7c6aff").opacity(0.4), radius: 10, y: 4)
                        }
                    }
                } else if isLoading {
                    VStack(spacing: 16) {
                        ProgressView()
                            .scaleEffect(1.4)
                            .tint(Color(hex: "7c6aff"))
                        Text("Generating your briefing...")
                            .foregroundColor(.secondary)
                    }
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 0) {
                            if let date = lastGenerated {
                                HStack {
                                    Image(systemName: "clock")
                                        .font(.caption)
                                    Text("Generated at \(date.formatted(date: .omitted, time: .shortened))")
                                        .font(.caption)
                                }
                                .foregroundColor(.secondary)
                                .padding(.horizontal, 20)
                                .padding(.top, 16)
                                .padding(.bottom, 12)
                            }

                            Text(briefing)
                                .font(.system(size: 15))
                                .lineSpacing(5)
                                .padding(20)
                        }
                    }
                }
            }
            .navigationTitle("Daily Briefing")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: generate) {
                        Image(systemName: "arrow.clockwise")
                            .foregroundColor(Color(hex: "a78bfa"))
                    }
                    .disabled(isLoading)
                }
            }
        }
        .onAppear {
            if briefing.isEmpty { generate() }
        }
    }

    private func generate() {
        isLoading = true
        Task {
            do {
                let result = try await api.fetchBriefing()
                await MainActor.run {
                    briefing = result
                    lastGenerated = Date()
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    briefing = "Could not connect to Barry. Make sure the server is running."
                    isLoading = false
                }
            }
        }
    }
}
