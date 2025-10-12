const taskInput = document.getElementById("taskInput");
const addBtn = document.getElementById("addBtn");
const taskList = document.getElementById("taskList");

// Lấy danh sách từ localStorage (nếu có)
let tasks = JSON.parse(localStorage.getItem("tasks")) || [];

// Hiển thị công việc
function renderTasks() {
  taskList.innerHTML = "";
  tasks.forEach((task, index) => {
    const li = document.createElement("li");
    li.className = task.completed ? "completed" : "";

    li.innerHTML = `
      <span onclick="toggleTask(${index})">${task.name}</span>
      <button onclick="deleteTask(${index})">❌</button>
    `;
    taskList.appendChild(li);
  });
}

// Thêm công việc
addBtn.addEventListener("click", () => {
  const taskName = taskInput.value.trim();
  if (taskName === "") return alert("Vui lòng nhập công việc!");
  tasks.push({ name: taskName, completed: false });
  taskInput.value = "";
  saveTasks();
  renderTasks();
});

// Đánh dấu hoàn thành
function toggleTask(index) {
  tasks[index].completed = !tasks[index].completed;
  saveTasks();
  renderTasks();
}

// Xóa công việc
function deleteTask(index) {
  tasks.splice(index, 1);
  saveTasks();
  renderTasks();
}

// Lưu vào localStorage
function saveTasks() {
  localStorage.setItem("tasks", JSON.stringify(tasks));
}

// Khởi tạo
renderTasks();
