import os
import json
import streamlit as st
import random

def load_questions():
    try:
        base_dir = os.path.dirname(__file__)  # folder where quiz_page.py is
        path = os.path.join(base_dir, "questions.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"⚠️ Could not load questions.json: {e}")
        return []

# ---------------------------
# Quiz logic
# ---------------------------
def run_quiz():
    st.markdown("<h1 style='text-align: center;'>🪐 MeteorShield Learning Zone</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; font-size:16px;'>Test your knowledge about asteroid impacts, mitigation strategies, and environmental effects!</p>",
        unsafe_allow_html=True
    )

    quiz_questions = load_questions()
    if not quiz_questions:
        st.warning("⚠️ No quiz questions available. Please check `questions.json`.")
        return

    random.shuffle(quiz_questions)  # shuffle for variety
    score = 0

    for idx, q in enumerate(quiz_questions):
        st.markdown(f"### Question {idx+1}")
        st.write(q.get("question", "❓ Missing question text"))

        options = q.get("options", [])
        if not options:
            st.warning("⚠️ This question has no options.")
            continue

        choice = st.radio("Choose an answer:", options, key=f"q{idx}")
        submitted = st.button("Submit Answer", key=f"submit{idx}")

        if submitted:
            if choice == q.get("answer"):
                st.success("✅ Correct!")
                score += 1
            else:
                st.error(f"❌ Incorrect. Correct answer: {q.get('answer', 'Unknown')}")

            # Safe explanation
            explanation = q.get("explanation", "No explanation available for this question.")
            st.info(explanation)

    # Final score
    st.markdown("---")
    st.markdown(f"### Your Score: {score} / {len(quiz_questions)}")

    if score == len(quiz_questions) and len(quiz_questions) > 0:
        st.balloons()
        st.success("🎉 Perfect score! You're an asteroid impact expert!")
    elif score >= max(1, len(quiz_questions)//2):
        st.info("👍 Good job! Try again to get a perfect score!")
    elif len(quiz_questions) > 0:
        st.warning("Keep learning! Check the simulation page to understand more.")
