import os
import json
import streamlit as st
import random

def load_questions():
    try:
        base_dir = os.path.dirname(__file__)
        path = os.path.join(base_dir, "questions.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"⚠️ Could not load questions.json: {e}")
        return []

def run_quiz():
    st.markdown("<h1 style='text-align: center;'>🪐 MeteorShield Learning Zone</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; font-size:16px;'>Test your knowledge about asteroid impacts, mitigation strategies, and environmental effects!</p>",
        unsafe_allow_html=True
    )

    quiz_questions = load_questions()
    if not quiz_questions:
        st.warning("⚠️ No quiz questions available.")
        return

    # Initialize session state
    if "question_index" not in st.session_state:
        st.session_state.question_index = 0
        st.session_state.score = 0
        random.shuffle(quiz_questions)
        st.session_state.quiz_questions = quiz_questions
        st.session_state.feedback = None
        st.session_state.explanation = None
        st.session_state.completed = False

    q_idx = st.session_state.question_index
    questions = st.session_state.quiz_questions

    # --- Show progress bar and score tracker ---
    progress = (q_idx / len(questions)) if len(questions) > 0 else 0
    st.progress(progress)
    st.caption(f"**Progress:** {q_idx}/{len(questions)} | **Score:** {st.session_state.score}")

    if not st.session_state.completed and q_idx < len(questions):
        q = questions[q_idx]
        st.markdown(f"### Question {q_idx + 1} of {len(questions)}")
        st.write(q["question"])

        choice = st.radio("Choose an answer:", q["options"], key=f"q_{q_idx}")
        submitted = st.button("Submit", key=f"submit_{q_idx}")

        # --- Handle submission ---
        if submitted and st.session_state.feedback is None:
            if choice == q["answer"]:
                st.session_state.feedback = "✅ Correct!"
                st.session_state.score += 1
            else:
                st.session_state.feedback = f"❌ Incorrect. Correct answer: {q['answer']}"
            st.session_state.explanation = q.get("explanation", "No explanation available.")

        # --- Show feedback and explanation after submission ---
        if st.session_state.feedback:
            if "✅" in st.session_state.feedback:
                st.success(st.session_state.feedback)
            else:
                st.error(st.session_state.feedback)
            st.info(st.session_state.explanation)

            # "Next Question" button appears after feedback
            if st.button("➡️ Next Question"):
                st.session_state.feedback = None
                st.session_state.explanation = None
                st.session_state.question_index += 1
                if st.session_state.question_index >= len(questions):
                    st.session_state.completed = True
                st.rerun()

    else:
        # --- Quiz completed ---
        st.session_state.completed = True
        st.markdown("---")
        st.markdown(f"### Your Final Score: {st.session_state.score} / {len(questions)}")

        if st.session_state.score == len(questions):
            st.balloons()
            st.success("🎉 Perfect score! You're an asteroid impact expert!")
        elif st.session_state.score >= len(questions)//2:
            st.info("👍 Good job! Try again to get a perfect score!")
        else:
            st.warning("Keep learning! Check the simulation page to understand more.")

        if st.button("🔁 Restart Quiz"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
