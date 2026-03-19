import SwiftUI

struct ChatView: View {
    @EnvironmentObject var api: BarryAPI
    @State private var messages: [ChatMessage] = [
        ChatMessage(role: .barry, content: "Hey! I'm Barry, your AI assistant.\n\nAsk me about your schedule, emails, tasks, or anything.", timestamp: Date())
    ]
    @State private var inputText = ""
    @State private var isStreaming = false
    @FocusState private var inputFocused: Bool

    let quickPrompts = ["Morning briefing", "My priorities", "Check calendar", "Urgent emails"]

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Barry")
                        .font(.system(size: 28, weight: .bold))
                    HStack(spacing: 5) {
                        Circle()
                            .fill(api.isOnline ? Color.green : Color(.systemGray4))
                            .frame(width: 7, height: 7)
                        Text(api.isOnline ? "Online" : "Offline")
                            .font(.system(size: 13))
                            .foregroundColor(.secondary)
                    }
                }
                Spacer()
                Button(action: resetChat) {
                    ZStack {
                        Circle()
                            .fill(Color(.systemGray6))
                            .frame(width: 36, height: 36)
                        Image(systemName: "arrow.counterclockwise")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(.black)
                    }
                }
            }
            .padding(.horizontal, 24)
            .padding(.top, 56)
            .padding(.bottom, 12)

            Divider()

            // Messages
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(messages) { msg in
                            MessageBubble(message: msg).id(msg.id)
                        }
                        if isStreaming {
                            ThinkingBubble().id("thinking")
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 14)
                }
                .onChange(of: messages.count) { _ in
                    withAnimation { proxy.scrollTo(messages.last?.id, anchor: .bottom) }
                }
            }

            // Quick prompts
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(quickPrompts, id: \.self) { p in
                        Button(p) { send(p) }
                            .font(.system(size: 13, weight: .medium))
                            .padding(.horizontal, 14)
                            .padding(.vertical, 7)
                            .background(Color(.systemGray6))
                            .foregroundColor(.black)
                            .cornerRadius(20)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
            }

            Divider()

            // Input bar
            HStack(alignment: .bottom, spacing: 10) {
                TextField("Message Barry...", text: $inputText, axis: .vertical)
                    .lineLimit(1...4)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(Color(.systemGray6))
                    .cornerRadius(20)
                    .focused($inputFocused)

                Button(action: sendFromInput) {
                    ZStack {
                        Circle()
                            .fill(inputText.trimmingCharacters(in: .whitespaces).isEmpty || isStreaming
                                  ? Color(.systemGray4) : Color.black)
                            .frame(width: 36, height: 36)
                        Image(systemName: "arrow.up")
                            .font(.system(size: 15, weight: .bold))
                            .foregroundColor(.white)
                    }
                }
                .disabled(inputText.trimmingCharacters(in: .whitespaces).isEmpty || isStreaming)
            }
            .padding(.horizontal, 16)
            .padding(.top, 8)
            .padding(.bottom, 100)
        }
        .background(Color.white.ignoresSafeArea())
    }

    private func sendFromInput() {
        let text = inputText.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty, !isStreaming else { return }
        inputText = ""
        send(text)
    }

    private func send(_ text: String) {
        inputFocused = false
        messages.append(ChatMessage(role: .user, content: text, timestamp: Date()))
        isStreaming = true
        var barryMsg = ChatMessage(role: .barry, content: "", timestamp: Date())

        api.chat(message: text) { chunk in
            if let idx = messages.firstIndex(where: { $0.id == barryMsg.id }) {
                messages[idx].content = chunk
            } else {
                isStreaming = false
                barryMsg = ChatMessage(role: .barry, content: chunk, timestamp: Date())
                messages.append(barryMsg)
                isStreaming = true
            }
        } onDone: {
            isStreaming = false
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
                        .fill(Color.black)
                        .frame(width: 30, height: 30)
                    Text("⚡").font(.system(size: 14))
                }
            }

            VStack(alignment: isUser ? .trailing : .leading, spacing: 3) {
                Text(message.content.isEmpty ? " " : message.content)
                    .font(.system(size: 15))
                    .lineSpacing(3)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(
                        isUser ? Color.black : Color(.systemGray6)
                    )
                    .foregroundColor(isUser ? .white : .black)
                    .clipShape(
                        RoundedCorners(tl: 16, tr: isUser ? 4 : 16, bl: isUser ? 16 : 4, br: 16)
                    )

                Text(message.timestamp, style: .time)
                    .font(.system(size: 10))
                    .foregroundColor(.secondary.opacity(0.6))
            }
            .frame(maxWidth: UIScreen.main.bounds.width * 0.70, alignment: isUser ? .trailing : .leading)

            if isUser {
                ZStack {
                    Circle()
                        .fill(Color(.systemGray5))
                        .frame(width: 30, height: 30)
                    Text("👤").font(.system(size: 13))
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
                    .fill(Color.black)
                    .frame(width: 30, height: 30)
                Text("⚡").font(.system(size: 14))
            }
            HStack(spacing: 5) {
                ForEach(0..<3, id: \.self) { i in
                    Circle()
                        .fill(Color.black.opacity(0.4))
                        .frame(width: 7, height: 7)
                        .scaleEffect(phase == Double(i) ? 1.4 : 0.8)
                        .animation(.easeInOut(duration: 0.4).repeatForever().delay(Double(i) * 0.15), value: phase)
                }
            }
            .padding(.horizontal, 18).padding(.vertical, 14)
            .background(Color(.systemGray6))
            .clipShape(RoundedCorners(tl: 16, tr: 16, bl: 4, br: 16))
            Spacer()
        }
        .onAppear { phase = 2 }
    }
}
