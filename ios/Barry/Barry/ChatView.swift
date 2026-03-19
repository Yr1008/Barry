import SwiftUI

struct ChatView: View {
    @EnvironmentObject var api: BarryAPI
    @State private var messages: [ChatMessage] = [
        ChatMessage(role: .barry, content: "Hey! I'm Barry, your personal AI assistant.\n\nI'm connected to your calendar, emails, WhatsApp, and iPhone. Ask me anything.", timestamp: Date())
    ]
    @State private var inputText = ""
    @State private var isStreaming = false
    @State private var scrollProxy: ScrollViewProxy?
    @FocusState private var inputFocused: Bool

    let quickPrompts = ["Morning briefing", "My priorities", "Check calendar", "Urgent emails"]

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Messages
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 16) {
                            ForEach(messages) { msg in
                                MessageBubble(message: msg)
                                    .id(msg.id)
                            }
                            if isStreaming {
                                ThinkingBubble()
                                    .id("thinking")
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                    }
                    .onAppear { scrollProxy = proxy }
                    .onChange(of: messages.count) { _ in
                        scrollToBottom(proxy: proxy)
                    }
                    .onChange(of: isStreaming) { _ in
                        scrollToBottom(proxy: proxy)
                    }
                }

                Divider().background(Color.white.opacity(0.1))

                // Quick prompts
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(quickPrompts, id: \.self) { prompt in
                            Button(prompt) {
                                send(prompt)
                            }
                            .font(.caption)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(Color.white.opacity(0.07))
                            .foregroundColor(.secondary)
                            .cornerRadius(20)
                            .overlay(RoundedRectangle(cornerRadius: 20).stroke(Color.white.opacity(0.1)))
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                }

                // Input
                HStack(alignment: .bottom, spacing: 10) {
                    TextField("Ask Barry anything...", text: $inputText, axis: .vertical)
                        .lineLimit(1...5)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .background(Color.white.opacity(0.07))
                        .cornerRadius(20)
                        .overlay(RoundedRectangle(cornerRadius: 20).stroke(Color.white.opacity(0.1)))
                        .focused($inputFocused)
                        .onSubmit { sendFromInput() }

                    Button(action: sendFromInput) {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 34))
                            .foregroundStyle(
                                inputText.trimmingCharacters(in: .whitespaces).isEmpty || isStreaming
                                ? Color.gray.opacity(0.4)
                                : LinearGradient(colors: [Color(hex: "7c6aff"), Color(hex: "a78bfa")],
                                                 startPoint: .topLeading, endPoint: .bottomTrailing)
                            )
                    }
                    .disabled(inputText.trimmingCharacters(in: .whitespaces).isEmpty || isStreaming)
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 12)
                .padding(.top, 4)
            }
            .background(Color(hex: "0a0a0f").ignoresSafeArea())
            .navigationTitle("Barry")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    HStack(spacing: 6) {
                        Circle()
                            .fill(api.isOnline ? Color.green : Color.red)
                            .frame(width: 8, height: 8)
                            .shadow(color: api.isOnline ? .green : .red, radius: 3)
                        Text(api.isOnline ? "Online" : "Offline")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: resetChat) {
                        Image(systemName: "trash")
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
    }

    private func sendFromInput() {
        let text = inputText.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty, !isStreaming else { return }
        inputText = ""
        send(text)
    }

    private func send(_ text: String) {
        guard !isStreaming else { return }
        inputFocused = false
        messages.append(ChatMessage(role: .user, content: text, timestamp: Date()))
        isStreaming = true

        var barryMsg = ChatMessage(role: .barry, content: "", timestamp: Date())

        api.chat(message: text) { chunk in
            if let idx = messages.firstIndex(where: { $0.id == barryMsg.id }) {
                messages[idx].content = chunk
            } else {
                isStreaming = false  // Remove thinking, add real bubble
                barryMsg = ChatMessage(role: .barry, content: chunk, timestamp: Date())
                messages.append(barryMsg)
                isStreaming = true
            }
        } onDone: {
            isStreaming = false
            Task { await api.refreshStatus() }
        }
    }

    private func resetChat() {
        Task {
            try? await api.resetConversation()
            await MainActor.run {
                messages = [ChatMessage(role: .barry, content: "Conversation reset. What can I help you with?", timestamp: Date())]
            }
        }
    }

    private func scrollToBottom(proxy: ScrollViewProxy) {
        withAnimation(.easeOut(duration: 0.2)) {
            if isStreaming {
                proxy.scrollTo("thinking", anchor: .bottom)
            } else if let last = messages.last {
                proxy.scrollTo(last.id, anchor: .bottom)
            }
        }
    }
}

// MARK: - Message Bubble
struct MessageBubble: View {
    let message: ChatMessage

    var isUser: Bool { message.role == .user }

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            if !isUser {
                ZStack {
                    RoundedRectangle(cornerRadius: 10)
                        .fill(LinearGradient(colors: [Color(hex: "7c6aff"), Color(hex: "a78bfa")],
                                             startPoint: .topLeading, endPoint: .bottomTrailing))
                        .frame(width: 32, height: 32)
                    Text("⚡").font(.system(size: 15))
                }
            }

            VStack(alignment: isUser ? .trailing : .leading, spacing: 3) {
                Text(isUser ? "You" : "Barry")
                    .font(.caption2)
                    .foregroundColor(.secondary)

                Text(message.content.isEmpty ? " " : message.content)
                    .font(.system(size: 15))
                    .lineSpacing(3)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(
                        isUser
                        ? LinearGradient(colors: [Color(hex: "7c6aff"), Color(hex: "6355e8")],
                                         startPoint: .topLeading, endPoint: .bottomTrailing)
                            .eraseToAnyView()
                        : Color(hex: "16161f").eraseToAnyView()
                    )
                    .foregroundColor(isUser ? .white : .primary)
                    .clipShape(
                        RoundedCorners(
                            tl: 14, tr: isUser ? 4 : 14,
                            bl: isUser ? 14 : 4, br: 14
                        )
                    )
                    .overlay(
                        RoundedCorners(tl: 14, tr: isUser ? 4 : 14, bl: isUser ? 14 : 4, br: 14)
                            .stroke(Color.white.opacity(isUser ? 0 : 0.07), lineWidth: 1)
                    )
                    .shadow(color: isUser ? Color(hex: "7c6aff").opacity(0.3) : .clear, radius: 8, y: 3)

                Text(message.timestamp, style: .time)
                    .font(.system(size: 10))
                    .foregroundColor(.secondary.opacity(0.6))
            }
            .frame(maxWidth: UIScreen.main.bounds.width * 0.72, alignment: isUser ? .trailing : .leading)

            if isUser {
                ZStack {
                    RoundedRectangle(cornerRadius: 10)
                        .fill(Color.white.opacity(0.07))
                        .frame(width: 32, height: 32)
                    Text("👤").font(.system(size: 15))
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: isUser ? .trailing : .leading)
    }
}

// MARK: - Thinking Bubble
struct ThinkingBubble: View {
    @State private var phase = 0.0

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            ZStack {
                RoundedRectangle(cornerRadius: 10)
                    .fill(LinearGradient(colors: [Color(hex: "7c6aff"), Color(hex: "a78bfa")],
                                         startPoint: .topLeading, endPoint: .bottomTrailing))
                    .frame(width: 32, height: 32)
                Text("⚡").font(.system(size: 15))
            }
            HStack(spacing: 5) {
                ForEach(0..<3, id: \.self) { i in
                    Circle()
                        .fill(Color(hex: "7c6aff"))
                        .frame(width: 7, height: 7)
                        .scaleEffect(phase == Double(i) ? 1.4 : 0.8)
                        .animation(.easeInOut(duration: 0.4).repeatForever().delay(Double(i) * 0.15), value: phase)
                }
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 14)
            .background(Color(hex: "16161f"))
            .clipShape(RoundedCorners(tl: 14, tr: 14, bl: 4, br: 14))
            Spacer()
        }
        .onAppear { phase = 2 }
    }
}
