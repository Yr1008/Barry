import SwiftUI

struct CalendarView: View {
    @State private var currentTime = Date()
    let timer = Timer.publish(every: 60, on: .main, in: .common).autoconnect()

    // Sample events — replace with API data
    let events: [CalendarEvent] = [
        CalendarEvent(title: "Learn Design", subtitle: "Development call",
                      emoji: "😸", startHour: 6.0, endHour: 6.5,
                      color: Color(hex: "FFCDD5")),
        CalendarEvent(title: "Design meeting\ncheck product", subtitle: "Design call",
                      emoji: "😊", startHour: 6.25, endHour: 7.0,
                      color: Color(hex: "B2EDD4")),
        CalendarEvent(title: "Slava\na Meet", subtitle: "06:45-07:30",
                      emoji: "😎", startHour: 6.75, endHour: 7.5,
                      color: Color(hex: "D4E8FF")),
    ]

    var body: some View {
        VStack(spacing: 0) {
            // MARK: Header
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text(currentTime.formatted(.dateTime.month(.wide).day()))
                        .font(.system(size: 38, weight: .bold))
                        .foregroundColor(.black)
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
            .padding(.bottom, 12)

            // MARK: Week strip
            WeekStrip(currentDate: currentTime)
                .padding(.horizontal, 24)
                .padding(.bottom, 16)

            // MARK: Timeline
            TimelineView(events: events)
        }
        .background(Color.white.ignoresSafeArea())
        .onReceive(timer) { _ in currentTime = Date() }
    }
}

// MARK: - Week Strip
struct WeekStrip: View {
    let currentDate: Date

    var weekDays: [Date] {
        let cal = Calendar.current
        let today = cal.startOfDay(for: currentDate)
        let weekday = cal.component(.weekday, from: today)
        let start = cal.date(byAdding: .day, value: -(weekday - 2), to: today)!
        return (0..<7).compactMap { cal.date(byAdding: .day, value: $0, to: start) }
    }

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(weekDays.enumerated()), id: \.offset) { _, day in
                let isToday = Calendar.current.isDateInToday(day)
                VStack(spacing: 4) {
                    Text(day.formatted(.dateTime.weekday(.narrow)))
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(isToday ? Color(hex: "FF4D4D") : .secondary)

                    ZStack {
                        if isToday {
                            Capsule()
                                .fill(Color(hex: "FF4D4D"))
                                .frame(width: 28, height: 4)
                                .offset(y: 10)
                        }
                    }
                }
                .frame(maxWidth: .infinity)
            }
        }
    }
}

// MARK: - Horizontal Timeline
struct TimelineView: View {
    let events: [CalendarEvent]

    let startHour: Double = 6.0
    let endHour: Double = 10.0
    let slotWidth: CGFloat = 80
    let rowHeight: CGFloat = 90
    let numRows = 3

    var totalHours: Double { endHour - startHour }
    var totalWidth: CGFloat { CGFloat(totalHours / 0.25) * slotWidth }

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            ZStack(alignment: .topLeading) {
                // Time labels + columns
                VStack(alignment: .leading, spacing: 0) {
                    // Time header
                    HStack(spacing: 0) {
                        ForEach(timeSlots, id: \.self) { label in
                            Text(label)
                                .font(.system(size: 12, weight: .medium))
                                .foregroundColor(.secondary)
                                .frame(width: slotWidth, alignment: .leading)
                        }
                    }
                    .padding(.leading, 4)
                    .padding(.bottom, 10)

                    // Grid rows
                    ZStack(alignment: .topLeading) {
                        // Horizontal grid lines
                        VStack(spacing: 0) {
                            ForEach(0..<numRows, id: \.self) { _ in
                                Rectangle()
                                    .fill(Color(.systemGray5).opacity(0.5))
                                    .frame(height: 1)
                                Spacer().frame(height: rowHeight - 1)
                            }
                        }

                        // Events
                        ForEach(events) { event in
                            EventBlock(event: event,
                                       startHour: startHour,
                                       slotWidth: slotWidth,
                                       rowHeight: rowHeight)
                        }
                    }
                    .frame(height: CGFloat(numRows) * rowHeight)
                }
                .padding(.horizontal, 16)
            }
            .frame(width: totalWidth + 32)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    var timeSlots: [String] {
        var slots: [String] = []
        var t = startHour
        while t <= endHour {
            let h = Int(t)
            let m = Int((t - Double(h)) * 60)
            slots.append(String(format: "%02d:%02d", h, m))
            t += 0.25
        }
        return slots
    }
}

// MARK: - Event Block
struct EventBlock: View {
    let event: CalendarEvent
    let startHour: Double
    let slotWidth: CGFloat
    let rowHeight: CGFloat

    var xOffset: CGFloat {
        CGFloat((event.startHour - startHour) / 0.25) * slotWidth + 16
    }

    var width: CGFloat {
        CGFloat((event.endHour - event.startHour) / 0.25) * slotWidth - 6
    }

    // Vertical position based on which "lane" it belongs to
    var yIndex: Int {
        if event.startHour < 6.25 { return 0 }
        if event.startHour < 6.75 { return 1 }
        return 2
    }

    var yOffset: CGFloat { CGFloat(yIndex) * rowHeight }

    var accentColor: Color {
        switch yIndex {
        case 0: return Color(hex: "FF4D4D")
        case 1: return Color(hex: "2ECC71")
        default: return Color(hex: "3B8BFF")
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(event.emoji).font(.system(size: 18))
                Spacer()
                Circle()
                    .stroke(Color.black.opacity(0.2), lineWidth: 1)
                    .frame(width: 16, height: 16)
            }

            Text(event.title)
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(.black)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)

            Spacer()

            HStack(spacing: 0) {
                Rectangle()
                    .fill(accentColor)
                    .frame(width: 2)
                    .cornerRadius(1)
                VStack(alignment: .leading, spacing: 1) {
                    Text(event.timeRangeString)
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(accentColor)
                    Text(event.subtitle)
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                }
                .padding(.leading, 4)
            }
        }
        .padding(10)
        .frame(width: width, height: rowHeight - 10, alignment: .topLeading)
        .background(event.color)
        .cornerRadius(14)
        .shadow(color: .black.opacity(0.05), radius: 4, y: 2)
        .offset(x: xOffset, y: yOffset)
    }
}
