import Foundation
import Combine

class BarryAPI: ObservableObject {
    @Published var baseURL: String {
        didSet { UserDefaults.standard.set(baseURL, forKey: "barry_url") }
    }
    @Published var status: BarryStatus?
    @Published var isOnline = false

    init() {
        self.baseURL = UserDefaults.standard.string(forKey: "barry_url") ?? "http://localhost:8000"
        Task { await refreshStatus() }
    }

    private func url(_ path: String) -> URL {
        URL(string: baseURL + path)!
    }

    // MARK: - Status
    @MainActor
    func refreshStatus() async {
        do {
            let (data, _) = try await URLSession.shared.data(from: url("/status"))
            status = try JSONDecoder().decode(BarryStatus.self, from: data)
            isOnline = true
        } catch {
            isOnline = false
        }
    }

    // MARK: - Chat (streaming)
    func chat(message: String, onChunk: @escaping (String) -> Void, onDone: @escaping () -> Void) {
        var req = URLRequest(url: url("/chat"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONEncoder().encode(["message": message, "stream": "true"])

        let delegate = StreamDelegate(onChunk: onChunk, onDone: onDone)
        let session = URLSession(configuration: .default, delegate: delegate, delegateQueue: nil)
        session.dataTask(with: req).resume()
    }

    // MARK: - Todos
    func fetchTodos() async throws -> [Todo] {
        let (data, _) = try await URLSession.shared.data(from: url("/todos"))
        return try JSONDecoder().decode(TodosResponse.self, from: data).todos
    }

    func addTodo(title: String, priority: Int = 2) async throws {
        var req = URLRequest(url: url("/todos"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["title": title, "priority": priority])
        _ = try await URLSession.shared.data(for: req)
    }

    func completeTodo(id: Int) async throws {
        var req = URLRequest(url: url("/todos/\(id)/complete"))
        req.httpMethod = "PUT"
        _ = try await URLSession.shared.data(for: req)
    }

    // MARK: - Briefing
    func fetchBriefing() async throws -> String {
        let (data, _) = try await URLSession.shared.data(from: url("/briefing"))
        return try JSONDecoder().decode(BriefingResponse.self, from: data).briefing
    }

    // MARK: - Reset
    func resetConversation() async throws {
        var req = URLRequest(url: url("/reset"))
        req.httpMethod = "POST"
        _ = try await URLSession.shared.data(for: req)
    }
}

// MARK: - SSE Stream Delegate
private class StreamDelegate: NSObject, URLSessionDataDelegate {
    let onChunk: (String) -> Void
    let onDone: () -> Void
    var buffer = ""

    init(onChunk: @escaping (String) -> Void, onDone: @escaping () -> Void) {
        self.onChunk = onChunk
        self.onDone = onDone
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        guard let text = String(data: data, encoding: .utf8) else { return }
        for line in text.components(separatedBy: "\n") {
            if line.hasPrefix("data: ") {
                let chunk = String(line.dropFirst(6))
                if chunk == "[DONE]" { continue }
                buffer += chunk
                let captured = buffer
                DispatchQueue.main.async { self.onChunk(captured) }
            }
        }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        DispatchQueue.main.async { self.onDone() }
    }
}
