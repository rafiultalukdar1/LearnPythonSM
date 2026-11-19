# Smart Job Application Screening System

def check_eligibility(applicant):
    if applicant["experience"] < 2:
        return False, "Not Enough Experience"

    if applicant["qualification"] not in ["Bachelor", "Master"]:
        return False, "Qualification Not Accepted"

    if len(applicant["skills"]) < 3:
        return False, "Insufficient Skills"

    return True, "Eligible"


def calculate_score(applicant):
    experience_score = min(applicant["experience"] * 5, 30)
    skill_score = len(applicant["skills"]) * 10
    qualification_score = 20 if applicant["qualification"] == "Master" else 10

    return experience_score + skill_score + qualification_score


def screen_application(applicant):

    # Check Eligibility
    eligible, message = check_eligibility(applicant)

    if not eligible:
        return {
            "status": "Rejected",
            "reason": message
        }

    # Calculate Applicant Score
    score = calculate_score(applicant)

    # Final Decision
    if score >= 80:
        decision = "Shortlisted"
    elif score >= 50:
        decision = "Under Review"
    else:
        decision = "Not Selected"

    return {
        "name": applicant["name"],
        "score": score,
        "status": decision
    }


# Applicant Information
applicant = {
    "name": "Rafiul",
    "experience": 5,
    "qualification": "Bachelor",
    "skills": ["Python", "JavaScript", "SQL", "Problem Solving"]
}

# Process Application
result = screen_application(applicant)

print(result)