import SwiftUI

struct BriefingView: View {
    @EnvironmentObject var api: BarryAPI
    @State private var briefing = ""
    @State private var isLoading = false
    @State private var lastGenerated: Date?

    var body: some View {
        NavigationView {
            ZStack {
                Color(.systemGray6).ignoresSafeArea()

                if briefing.isEmpty && !isLoading {
                    VStack(spacing: 20) {
                        Image(systemName: "sun.max.fill")
                            .font(.system(size: 54))
                            .foregroundStyle(LinearGradient(colors: [.yellow, .orange],
                                                            startPoint: .top, endPoint: .bottom))
                        Text("Daily Briefing").font(.title2).bold()
                        Text("Get a summary of your day, priorities, and what needs your attention.")
                            .foregroundColor(.secondary).multilineTextAlignment(.center)
                            .padding(.horizontal, 40)
                        Button(action: generate) {
                            Label("Generate", systemImage: "bolt.fill")
                                .font(.headline).foregroundColor(.white)
                                .padding(.horizontal, 28).padding(.vertical, 14)
                                .background(Color.black).cornerRadius(14)
                        }
                    }
                } else if isLoading {
                    VStack(spacing: 14) {
                        ProgressView()
                        Text("Generating...").foregroundColor(.secondary)
                    }
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 0) {
                            if let d = lastGenerated {
                                Label(d.formatted(date: .omitted, time: .shortened), systemImage: "clock")
                                    .font(.caption).foregroundColor(.secondary)
                                    .padding(.horizontal, 20).padding(.top, 16).padding(.bottom, 12)
                            }
                            Text(briefing)
                                .font(.system(size: 15)).lineSpacing(5)
                                .padding(20)
                        }
                        .background(Color.white).cornerRadius(16)
                        .shadow(color: .black.opacity(0.05), radius: 8, y: 3)
                        .padding(16)
                    }
                }
            }
            .navigationTitle("Briefing")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: generate) {
                        Image(systemName: "arrow.clockwise").foregroundColor(.black)
                    }
                    .disabled(isLoading)
                }
            }
        }
        .onAppear { if briefing.isEmpty { generate() } }
    }

    private func generate() {
        isLoading = true
        Task {
            let result = (try? await api.fetchBriefing()) ?? "Could not connect to Barry."
            await MainActor.run { briefing = result; lastGenerated = Date(); isLoading = false }
        }
    }
}
