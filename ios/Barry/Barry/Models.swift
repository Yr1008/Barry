import Foundation
import SwiftUI

// MARK: - Chat
struct ChatMessage: Identifiable {
    let id = UUID()
    let role: Role
    var content: String
    let timestamp: Date

    enum Role { case user, barry }
}

// MARK: - Todo
struct Todo: Identifiable, Codable {
    let id: Int
    let title: String
    let priority: Int
    let dueDate: String?
    let aiReason: String?
    let completed: Bool

    enum CodingKeys: String, CodingKey {
        case id, title, priority, completed
        case dueDate = "due_date"
        case aiReason = "ai_reason"
    }

    var emoji: String {
        let emojis = ["🌟", "📌", "🎯", "⚡", "🔑", "📋", "🚀", "💡", "🌿", "🎨"]
        return emojis[abs(id) % emojis.count]
    }
}

struct TodosResponse: Codable {
    let todos: [Todo]
}

// MARK: - Calendar Event
struct CalendarEvent: Identifiable {
    let id = UUID()
    let title: String
    let subtitle: String
    let emoji: String
    let startHour: Double   // e.g. 6.0 = 06:00, 6.5 = 06:30
    let endHour: Double
    let color: Color

    var startTimeString: String {
        let h = Int(startHour)
        let m = Int((startHour - Double(h)) * 60)
        return String(format: "%02d:%02d", h, m)
    }

    var endTimeString: String {
        let h = Int(endHour)
        let m = Int((endHour - Double(h)) * 60)
        return String(format: "%02d:%02d", h, m)
    }

    var timeRangeString: String { "\(startTimeString)-\(endTimeString)" }
}

// MARK: - Status
struct BarryStatus: Codable {
    let name: String
    let owner: String
    let timezone: String
    let connectors: Connectors
    let memory: Memory
    let lastEvents: Int
    let lastEmails: Int

    enum CodingKeys: String, CodingKey {
        case name, owner, timezone, connectors, memory
        case lastEvents = "last_events"
        case lastEmails = "last_emails"
    }
}

struct Connectors: Codable {
    let googleCalendar: Bool
    let icloud: Bool
    let email: Bool
    let whatsapp: Bool
    let iphoneShortcuts: Bool

    enum CodingKeys: String, CodingKey {
        case icloud, email, whatsapp
        case googleCalendar = "google_calendar"
        case iphoneShortcuts = "iphone_shortcuts"
    }
}

struct Memory: Codable {
    let todos: Int
    let facts: Int
    let toneProfiles: Int
    let conversationHistory: Int

    enum CodingKeys: String, CodingKey {
        case todos, facts
        case toneProfiles = "tone_profiles"
        case conversationHistory = "conversation_history"
    }
}

// MARK: - Briefing
struct BriefingResponse: Codable {
    let briefing: String
}
