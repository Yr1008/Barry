import SwiftUI

struct TodosView: View {
    @EnvironmentObject var api: BarryAPI
    @State private var todos: [Todo] = []
    @State private var isLoading = true
    @State private var showAdd = false
    @State private var newTodoTitle = ""
    @State private var newTodoPriority = 2

    var body: some View {
        NavigationView {
            ZStack {
                Color(hex: "0a0a0f").ignoresSafeArea()

                if isLoading {
                    ProgressView().tint(Color(hex: "7c6aff"))
                } else if todos.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 60))
                            .foregroundStyle(LinearGradient(
                                colors: [Color(hex: "7c6aff"), Color(hex: "a78bfa")],
                                startPoint: .top, endPoint: .bottom))
                        Text("All caught up!")
                            .font(.title2).bold()
                        Text("No pending todos.")
                            .foregroundColor(.secondary)
                    }
                } else {
                    List {
                        ForEach(todos) { todo in
                            TodoRow(todo: todo, onComplete: {
                                completeTodo(todo)
                            })
                            .listRowBackground(Color(hex: "111118"))
                            .listRowSeparatorTint(Color.white.opacity(0.07))
                        }
                    }
                    .listStyle(.plain)
                    .scrollContentBackground(.hidden)
                }
            }
            .navigationTitle("Todos")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { showAdd = true }) {
                        Image(systemName: "plus.circle.fill")
                            .foregroundStyle(LinearGradient(
                                colors: [Color(hex: "7c6aff"), Color(hex: "a78bfa")],
                                startPoint: .topLeading, endPoint: .bottomTrailing))
                    }
                }
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: load) {
                        Image(systemName: "arrow.clockwise")
                            .foregroundColor(.secondary)
                    }
                }
            }
            .sheet(isPresented: $showAdd) {
                AddTodoSheet(isPresented: $showAdd, onAdd: addTodo)
            }
        }
        .onAppear(perform: load)
    }

    private func load() {
        isLoading = true
        Task {
            let result = (try? await api.fetchTodos()) ?? []
            await MainActor.run {
                todos = result
                isLoading = false
            }
        }
    }

    private func completeTodo(_ todo: Todo) {
        Task {
            try? await api.completeTodo(id: todo.id)
            await MainActor.run {
                todos.removeAll { $0.id == todo.id }
            }
        }
    }

    private func addTodo(title: String, priority: Int) {
        Task {
            try? await api.addTodo(title: title, priority: priority)
            load()
        }
    }
}

// MARK: - Todo Row
struct TodoRow: View {
    let todo: Todo
    let onComplete: () -> Void
    @State private var pressed = false

    var priorityColor: Color {
        switch todo.priority {
        case 1: return .red
        case 2: return .orange
        case 3: return .yellow
        default: return .gray
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Button(action: {
                withAnimation(.spring(response: 0.3)) { pressed = true }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { onComplete() }
            }) {
                ZStack {
                    Circle()
                        .stroke(priorityColor.opacity(0.6), lineWidth: 1.5)
                        .frame(width: 22, height: 22)
                    if pressed {
                        Image(systemName: "checkmark")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundColor(priorityColor)
                    }
                }
            }
            .padding(.top, 1)

            VStack(alignment: .leading, spacing: 4) {
                Text(todo.title)
                    .font(.system(size: 15, weight: .medium))
                    .strikethrough(pressed)

                if let reason = todo.aiReason {
                    Text(reason)
                        .font(.caption)
                        .foregroundColor(Color(hex: "a78bfa"))
                        .italic()
                }

                if let due = todo.dueDate {
                    Label(String(due.prefix(10)), systemImage: "calendar")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            Spacer()

            Text(todo.priorityEmoji)
                .font(.system(size: 14))
        }
        .padding(.vertical, 10)
        .padding(.horizontal, 4)
        .opacity(pressed ? 0.4 : 1)
    }
}

// MARK: - Add Todo Sheet
struct AddTodoSheet: View {
    @Binding var isPresented: Bool
    let onAdd: (String, Int) -> Void

    @State private var title = ""
    @State private var priority = 2
    @FocusState private var focused: Bool

    let priorities = [(1, "🔴 Critical"), (2, "🟠 High"), (3, "🟡 Medium"), (4, "⚪ Low")]

    var body: some View {
        NavigationView {
            Form {
                Section("Task") {
                    TextField("What needs to be done?", text: $title, axis: .vertical)
                        .lineLimit(1...3)
                        .focused($focused)
                }
                Section("Priority") {
                    Picker("Priority", selection: $priority) {
                        ForEach(priorities, id: \.0) { p in
                            Text(p.1).tag(p.0)
                        }
                    }
                    .pickerStyle(.segmented)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Color(hex: "0a0a0f"))
            .navigationTitle("New Todo")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { isPresented = false }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        guard !title.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                        onAdd(title, priority)
                        isPresented = false
                    }
                    .bold()
                    .disabled(title.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
        .onAppear { focused = true }
    }
}
