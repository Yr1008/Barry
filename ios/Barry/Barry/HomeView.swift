import SwiftUI

struct HomeView: View {
    @EnvironmentObject var api: BarryAPI
    @EnvironmentObject var appState: AppState
    @State private var todos: [Todo] = []
    @State private var currentTime = Date()
    @State private var nextTaskOffset: Int = 0

    let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    // Sample meetings (replace with API data)
    let meetingEmojis = ["🧶", "🍌", "🎯"]
    let meetingCount = 2

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 0) {

                // MARK: Header
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(currentTime.formatted(.dateTime.month(.wide).day()))
                            .font(.system(size: 38, weight: .bold, design: .default))
                            .foregroundColor(.black)
                        Text("\(meetingCount) Meeting\(meetingCount == 1 ? "" : "s")")
                            .font(.system(size: 20, weight: .regular))
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                    Button {} label: {
                        Image(systemName: "line.3.horizontal")
                            .font(.system(size: 22, weight: .medium))
                            .foregroundColor(.black)
                    }
                }
                .padding(.horizontal, 24)
                .padding(.top, 56)

                // MARK: Meeting Avatars
                HStack(spacing: -10) {
                    ForEach(Array(meetingEmojis.prefix(meetingCount).enumerated()), id: \.offset) { _, emoji in
                        AvatarCircle(emoji: emoji)
                    }
                }
                .padding(.horizontal, 24)
                .padding(.top, 18)

                // MARK: Clock Wheel
                ClockWheelView(currentTime: currentTime, nextTaskOffset: nextTaskOffset)
                    .frame(maxWidth: .infinity)
                    .padding(.top, 10)

                // MARK: Bottom Cards
                HStack(alignment: .top, spacing: 12) {
                    TasksMiniCard(todos: todos, onSeeAll: { appState.selectedTab = 0 })

                    MeetingCountdownCard()
                }
                .padding(.horizontal, 20)
                .padding(.top, 16)
                .padding(.bottom, 120)
            }
        }
        .background(Color.white.ignoresSafeArea())
        .onReceive(timer) { _ in currentTime = Date() }
        .onAppear {
            Task {
                if let t = try? await api.fetchTodos() { todos = t }
            }
        }
    }
}

// MARK: - Avatar Circle
struct AvatarCircle: View {
    let emoji: String
    var body: some View {
        ZStack {
            Circle()
                .fill(Color(.systemGray5))
                .frame(width: 46, height: 46)
            Text(emoji).font(.system(size: 22))
        }
        .overlay(Circle().stroke(Color.white, lineWidth: 2.5))
        .shadow(color: .black.opacity(0.06), radius: 4, y: 2)
    }
}

// MARK: - Clock Wheel
struct ClockWheelView: View {
    let currentTime: Date
    let nextTaskOffset: Int

    private let diameter: CGFloat = 240
    private let dotCount = 60
    private let eventDots: [(position: Int, color: Color)] = [
        (20, Color(hex: "FFD600")),
        (35, Color(hex: "FF4D4D"))
    ]

    var nextTaskTime: String {
        let calendar = Calendar.current
        var comps = calendar.dateComponents([.hour, .minute], from: currentTime)
        comps.minute = (comps.minute ?? 0) + 30 + nextTaskOffset
        let future = calendar.date(from: comps) ?? currentTime
        return future.formatted(.dateTime.hour(.twoDigits(amPM: .omitted)).minute())
    }

    var countdownString: String {
        let mins = 30 - (Calendar.current.component(.minute, from: currentTime) % 30)
        let secs = 60 - Calendar.current.component(.second, from: currentTime)
        let m = secs == 60 ? mins : mins - 1
        let s = secs == 60 ? 0 : secs
        return String(format: "00:%02d:%02d", max(0, m), max(0, s))
    }

    var body: some View {
        ZStack {
            // Dotted ring
            Canvas { context, size in
                let center = CGPoint(x: size.width / 2, y: size.height / 2)
                let radius = diameter / 2

                for i in 0..<dotCount {
                    let angle = Double(i) / Double(dotCount) * 2 * .pi - .pi / 2
                    let x = center.x + cos(angle) * radius
                    let y = center.y + sin(angle) * radius

                    let isEvent = eventDots.first(where: { $0.position == i })

                    var dotColor = Color.black.opacity(0.12)
                    var dotSize: CGFloat = 3

                    if let ev = isEvent {
                        dotColor = ev.color
                        dotSize = 8
                    }

                    context.fill(
                        Path(ellipseIn: CGRect(x: x - dotSize/2, y: y - dotSize/2, width: dotSize, height: dotSize)),
                        with: .color(dotColor)
                    )
                }

                // Bottom filled arc (progress)
                let startA = Double.pi * 0.2
                let endA = Double.pi * 0.8
                var arcPath = Path()
                arcPath.addArc(center: center, radius: radius - 1,
                               startAngle: .radians(startA), endAngle: .radians(endA), clockwise: false)
                context.stroke(arcPath, with: .color(.black.opacity(0.7)), style: StrokeStyle(lineWidth: 2.5, lineCap: .round))
            }
            .frame(width: diameter + 40, height: diameter + 40)

            // Center content
            VStack(spacing: 2) {
                Text("Next Task")
                    .font(.system(size: 13, weight: .regular))
                    .foregroundColor(.secondary)

                // Nav row
                HStack(spacing: 14) {
                    Button {} label: {
                        Image(systemName: "backward.end.fill")
                            .font(.system(size: 13))
                            .foregroundColor(.black.opacity(0.4))
                    }
                    Text(nextTaskTime)
                        .font(.system(size: 46, weight: .bold, design: .rounded))
                        .foregroundColor(.black)
                    Button {} label: {
                        Image(systemName: "forward.end.fill")
                            .font(.system(size: 13))
                            .foregroundColor(.black.opacity(0.4))
                    }
                }

                Text(countdownString)
                    .font(.system(size: 13, weight: .regular, design: .monospaced))
                    .foregroundColor(.secondary)
            }
        }
    }
}

// MARK: - Tasks Mini Card
struct TasksMiniCard: View {
    let todos: [Todo]
    let onSeeAll: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Tasks")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(.black)
                Spacer()
                Button(action: onSeeAll) {
                    Image(systemName: "plus")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(.black)
                }
            }
            .padding(.horizontal, 14)
            .padding(.top, 14)

            Divider().padding(.horizontal, 14).padding(.top, 10)

            VStack(alignment: .leading, spacing: 0) {
                let shown = todos.prefix(4)
                if shown.isEmpty {
                    Text("No tasks")
                        .font(.system(size: 13))
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                } else {
                    ForEach(Array(shown)) { todo in
                        MiniTodoRow(todo: todo)
                    }
                }
            }
            .padding(.top, 4)

            if todos.count > 4 {
                Button(action: onSeeAll) {
                    Text("See All")
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal, 14)
                .padding(.bottom, 12)
                .padding(.top, 4)
            } else {
                Spacer(minLength: 12)
            }
        }
        .frame(maxWidth: .infinity, minHeight: 180, alignment: .topLeading)
        .background(Color.white)
        .cornerRadius(20)
        .shadow(color: .black.opacity(0.07), radius: 12, y: 4)
    }
}

struct MiniTodoRow: View {
    let todo: Todo
    @State private var checked = false

    var body: some View {
        HStack(spacing: 8) {
            Text(todo.emoji)
                .font(.system(size: 13))
            Text(todo.title)
                .font(.system(size: 13))
                .foregroundColor(.black)
                .lineLimit(1)
            Spacer()
            Button {
                withAnimation(.spring(response: 0.3)) { checked.toggle() }
            } label: {
                ZStack {
                    RoundedRectangle(cornerRadius: 4)
                        .stroke(Color(.systemGray4), lineWidth: 1.5)
                        .frame(width: 16, height: 16)
                    if checked {
                        Image(systemName: "checkmark")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundColor(.black)
                    }
                }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 7)
    }
}

// MARK: - Meeting Countdown Card
struct MeetingCountdownCard: View {
    @State private var secondsLeft = 20 * 60 + 56
    let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    var minutesLeft: Int { secondsLeft / 60 }
    var secsLeft: Int { secondsLeft % 60 }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 6) {
                Text("🗓️")
                    .font(.system(size: 16))
                Text("You Have\na Meeting")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(.black)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer()
                Circle()
                    .stroke(Color.black.opacity(0.2), lineWidth: 1.5)
                    .frame(width: 18, height: 18)
            }
            .padding(.horizontal, 14)
            .padding(.top, 14)

            Spacer()

            HStack(alignment: .firstTextBaseline, spacing: 0) {
                Text(String(format: "%02d", minutesLeft))
                    .font(.system(size: 48, weight: .bold, design: .rounded))
                    .foregroundColor(.black)
                Text(":")
                    .font(.system(size: 40, weight: .bold))
                    .foregroundColor(.black.opacity(0.5))
                    .offset(y: -4)
                Text(String(format: "%02d", secsLeft))
                    .font(.system(size: 48, weight: .bold, design: .rounded))
                    .foregroundColor(.black.opacity(0.5))
            }
            .padding(.horizontal, 14)

            Text("Development call")
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(.black.opacity(0.7))
                .padding(.horizontal, 14)
                .padding(.bottom, 14)
                .padding(.top, 2)
        }
        .frame(maxWidth: .infinity, minHeight: 180)
        .background(Color(hex: "FFE600"))
        .cornerRadius(20)
        .shadow(color: Color(hex: "FFE600").opacity(0.4), radius: 12, y: 4)
        .onReceive(timer) { _ in if secondsLeft > 0 { secondsLeft -= 1 } }
    }
}
