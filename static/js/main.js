console.log("main.js loaded")

let selectedTaskKey = "";
  function selectTask(taskKey) {
          selectedTaskKey = taskKey;
          const task = allTasks[taskKey];

          if (task) {
              document.getElementById("selectedTaskDesc").innerText = task.description;
          } else {
              document.getElementById("selectedTaskDesc").innerText = "Invalid task selected.";
          }

          // Disable the submit button until tests are run again
          document.getElementById("submitBtn").disabled = true;

          // Lock in the AI toggle once a task is selected
          document.getElementById("aiToggle").disabled = true;

          document.getElementById("modelToggle").classList.add("model-locked");

          // 🔒 Lock model selection buttons
          document.querySelectorAll('input[name="modelOption"]').forEach(btn => {
              btn.disabled = true;
          });

          // ✅ Send a request to the server to set the start_time in the session
          fetch('/select_task', {
              method: 'POST',
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
              body: `task_key=${encodeURIComponent(taskKey)}`
          })
          .then(response => response.json())
          .then(data => {
              console.log("Task selected and start_time set:", data);
          })
          .catch(error => {
              console.error("Error setting start_time:", error);
          });
      }




        function getHint() {
            console.log("➡️ getHint() triggered");
            let userCode = editor.getValue();
            if (!selectedTaskKey) {
              alert("Please select a task first.");
              return;
            }

            // ✅ GET SELECTED MODEL + PROVIDER
            let modelInfo = document.querySelector('input[name="modelOption"]:checked').value;
            let [provider, model] = modelInfo.split(":");

            fetch('/get_hint', {
              method: 'POST',
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
              body: `user_code=${encodeURIComponent(userCode)}&selectedTask=${encodeURIComponent(selectedTaskKey)}&provider=${provider}&model=${model}`
            })
            .then(response => response.json())
            .then(data => {
              document.getElementById("code_hint").innerText = data.hint;
            });
          }


        function runCode() {
            let userCode = editor.getValue();
            fetch('/run_code', {
                method: 'POST',
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: `user_code=${encodeURIComponent(userCode)}`
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById("run_result").innerText = data.output;
            });
        }


        function testCode() {
            let userCode = editor.getValue();
            if (!selectedTaskKey) {
                alert("Please select a task first.");
                return;
            }

            fetch('/execute_code', {
                method: 'POST',
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: `user_code=${encodeURIComponent(userCode)}&task_key=${encodeURIComponent(selectedTaskKey)}`
            })
            .then(response => response.json())
            .then(data => {
                let resultContainer = document.getElementById("execution_result");
                resultContainer.innerHTML = "";

                data.results.forEach(test => {
                    let status = test.passed ? "✅ Passed" : "❌ Failed";
                    resultContainer.innerHTML += `<p><b>Input:</b> ${test.input} <br> <b>Expected:</b> ${test.expected} <br> <b>Output:</b> ${test.actual} <br> <b>Status:</b> ${status}</p><hr>`;
                });

                // Enable or disable the submit button
                const submitBtn = document.getElementById("submitBtn");
                if (data.all_tests_passed) {
                    submitBtn.disabled = false;
                } else {
                    submitBtn.disabled = true;
                }
            });
        }


        function refreshCheckmarks() {
          const usedAI = document.getElementById("aiToggle").checked;

          for (const key in allTasks) {
              const span = document.getElementById("check-" + key);
              if (completedByMode.has(`${key}_${usedAI}`)) {
                  span.innerText = "✅";
              } else {
                  span.innerText = "";
              }
          }
      }
      refreshCheckmarks();



        function submitCode() {
        let task = selectedTaskKey;
        let userCode = editor.getValue();
        let hint = document.getElementById("code_hint").innerText;
        let usedAI = document.getElementById("aiToggle").checked;
        let modelInfo = document.querySelector('input[name="modelOption"]:checked').value;

        let [provider, model] = modelInfo.split(":");

        if (!task) {
            alert("Please select a task first.");
            return;
        }
        fetch('/submit_code', {
            method: 'POST',
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: `task=${encodeURIComponent(task)}&user_code=${encodeURIComponent(userCode)}&hint=${encodeURIComponent(hint)}&used_ai=${usedAI}&provider=${encodeURIComponent(provider)}&model=${encodeURIComponent(model)}`
        })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
        });
    }


        // Initialize CodeMirror
        var editor = CodeMirror.fromTextArea(document.getElementById("code_editor"), {
            mode: "python",
            theme: "dracula",
            lineNumbers: true
        });

        // Toggle hint button based on AI assistance checkbox
        document.getElementById('aiToggle').addEventListener('change', function () {
        document.getElementById('hintBtn').disabled = !this.checked;
        refreshCheckmarks();
});