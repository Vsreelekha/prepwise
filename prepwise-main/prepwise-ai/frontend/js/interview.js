const token = localStorage.getItem("token")

let sessionId = null
let currentQuestionId = null

async function startInterview(jobRoleId){

    const response = await fetch(
        "http://127.0.0.1:8000/api/interview/start",
        {
            method:"POST",

            headers:{
                "Content-Type":"application/json",
                "Authorization":`Bearer ${token}`
            },

            body:JSON.stringify({
                job_role_id:jobRoleId
            })
        }
    )

    const data = await response.json()

    sessionId = data.session_id

    loadQuestion()
}


async function loadQuestion(){

    const response = await fetch(
        `http://127.0.0.1:8000/api/interview/question/${sessionId}`,
        {
            headers:{
                "Authorization":`Bearer ${token}`
            }
        }
    )

    const data = await response.json()

    if(data.error){
        alert("Interview Completed")
        window.location.href = "analytics.html"
        return
    }

    currentQuestionId = data.question_id

    document.getElementById("question").innerText =
        data.question_text

    document.getElementById("difficulty").innerText =
        data.difficulty

    document.getElementById("skill").innerText =
        data.skill_tested
}


async function submitAnswer(){

    const answer =
        document.getElementById("answer").value

    const response = await fetch(
        "http://127.0.0.1:8000/api/interview/answer",
        {
            method:"POST",

            headers:{
                "Content-Type":"application/json",
                "Authorization":`Bearer ${token}`
            },

            body:JSON.stringify({
                session_id:sessionId,
                question_id:currentQuestionId,
                user_answer:answer
            })
        }
    )

    const data = await response.json()

    alert(
        `Score: ${data.ai_score}\n\n${data.feedback}`
    )

    document.getElementById("answer").value = ""

    if(data.next_question_available){
        loadQuestion()
    }
    else{
        alert("Interview Completed")
        window.location.href = "analytics.html"
    }

}