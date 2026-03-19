import Foundation

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

    var priorityColor: String {
        switch priority {
        case 1: return "red"
        case 2: return "orange"
        case 3: return "yellow"
        default: return "gray"
        }
    }

    var priorityEmoji: String {
        switch priority {
        case 1: return "🔴"
        case 2: return "🟠"
        case 3: return "🟡"
        default: return "⚪"
        }
    }
}

struct TodosResponse: Codable {
    let todos: [Todo]
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
