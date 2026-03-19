import SwiftUI

struct TodosView: View {
    @EnvironmentObject var api: BarryAPI
    @State private var todos: [Todo] = []
    @State private var isLoading = true

    var body: some View {
        NavigationView {
            ZStack {
                Color(.systemGray6).ignoresSafeArea()

                if isLoading {
                    ProgressView()
                } else if todos.isEmpty {
                    VStack(spacing: 14) {
                        Text("✅").font(.system(size: 54))
                        Text("All caught up!").font(.title2).bold()
                        Text("No pending tasks.").foregroundColor(.secondary)
                    }
                } else {
                    List {
                        ForEach(todos) { todo in
                            TodoRow(todo: todo) { completeTodo(todo) }
                                .listRowBackground(Color.white)
                                .listRowInsets(EdgeInsets(top: 0, leading: 16, bottom: 0, trailing: 16))
                        }
                    }
                    .listStyle(.insetGrouped)
                    .scrollContentBackground(.hidden)
                }
            }
            .navigationTitle("Tasks")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: load) {
                        Image(systemName: "arrow.clockwise").foregroundColor(.black)
                    }
                }
            }
        }
        .onAppear(perform: load)
    }

    private func load() {
        isLoading = true
        Task {
            let result = (try? await api.fetchTodos()) ?? []
            await MainActor.run { todos = result; isLoading = false }
        }
    }

    private func completeTodo(_ todo: Todo) {
        Task {
            try? await api.completeTodo(id: todo.id)
            await MainActor.run { todos.removeAll { $0.id == todo.id } }
        }
    }
}

struct TodoRow: View {
    let todo: Todo
    let onComplete: () -> Void
    @State private var checked = false

    var priorityColor: Color {
        switch todo.priority {
        case 1: return .red
        case 2: return .orange
        case 3: return Color(hex: "FFD600")
        default: return Color(.systemGray4)
        }
    }

    var body: some View {
        HStack(spacing: 12) {
            Button {
                withAnimation(.spring(response: 0.3)) { checked = true }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { onComplete() }
            } label: {
                ZStack {
                    Circle()
                        .stroke(priorityColor, lineWidth: 1.5)
                        .frame(width: 24, height: 24)
                    if checked {
                        Circle().fill(priorityColor).frame(width: 14, height: 14)
                    }
                }
            }

            Text(todo.emoji).font(.system(size: 16))

            VStack(alignment: .leading, spacing: 2) {
                Text(todo.title)
                    .font(.system(size: 15))
                    .strikethrough(checked)
                    .foregroundColor(checked ? .secondary : .black)
                if let reason = todo.aiReason {
                    Text(reason)
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                        .italic()
                }
            }
            Spacer()
        }
        .padding(.vertical, 12)
        .opacity(checked ? 0.4 : 1)
        .animation(.easeInOut(duration: 0.2), value: checked)
    }
}

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
                    .pickerStyle(.inline)
                    .labelsHidden()
                }
            }
            .navigationTitle("New Task")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { isPresented = false } }
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
