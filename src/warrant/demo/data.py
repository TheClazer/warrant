"""Content of the fictional Northfield course portal."""

from __future__ import annotations

STUDENT = {"name": "Aarav Mehta", "id": "NF-24-0117", "programme": "B.Tech Computer Science, Year 3"}

COURSES = [
    {"code": "CS301", "title": "Operating Systems", "lecturer": "Dr. Ines Kovac", "room": "Block C, Room 204"},
    {
        "code": "MA204",
        "title": "Probability and Statistics",
        "lecturer": "Prof. Ravi Shenoy",
        "room": "Block A, Room 112",
    },
    {"code": "HS110", "title": "Technical Writing", "lecturer": "Ms. Laura Chen", "room": "Library Seminar Room 3"},
]

ANNOUNCEMENTS = [
    {
        "id": "a1",
        "course": "CS301",
        "date": "2026-10-26",
        "title": "Midterm venue change",
        "body": "The CS301 midterm on Thursday 29 October moves to Hall B. Start time stays 10:00. Bring your ID card.",
    },
    {
        "id": "a2",
        "course": "CS301",
        "date": "2026-10-25",
        "title": "Lab 4 deadline extended",
        "body": "Lab 4 (process scheduler) is now due Friday 30 October, 23:59, because the lab server was down on Monday.",
    },
    {
        "id": "a3",
        "course": "MA204",
        "date": "2026-10-24",
        "title": "Problem set 5 released",
        "body": "Problem set 5 covers conditional probability and Bayes' rule. It is due Monday 2 November.",
    },
    {
        "id": "a4",
        "course": "HS110",
        "date": "2026-10-23",
        "title": "Guest lecture moved",
        "body": "Tuesday's guest lecture on writing for engineers moves to Room 2 of the Library Annex.",
    },
    {
        "id": "a5",
        "course": "MA204",
        "date": "2026-10-20",
        "title": "Office hours",
        "body": "Office hours this week are Wednesday 15:00 to 17:00 in Block A, Room 118.",
    },
]

ASSIGNMENTS = [
    {
        "id": "cs301-lab4",
        "course": "CS301",
        "title": "Lab 4: process scheduler",
        "due": "2026-10-30 23:59",
        "status": "Not submitted",
    },
    {
        "id": "ma204-ps5",
        "course": "MA204",
        "title": "Problem set 5",
        "due": "2026-11-02 23:59",
        "status": "Not submitted",
    },
    {
        "id": "hs110-essay2",
        "course": "HS110",
        "title": "Essay 2: explaining a system to a non-expert",
        "due": "2026-11-06 17:00",
        "status": "Draft saved",
    },
    {
        "id": "cs301-lab3",
        "course": "CS301",
        "title": "Lab 3: shell",
        "due": "2026-10-16 23:59",
        "status": "Submitted, graded",
    },
]

GRADES = [
    {"course": "CS301", "item": "Lab 3: shell", "score": "18 / 20"},
    {"course": "MA204", "item": "Problem set 4", "score": "41 / 50"},
    {"course": "HS110", "item": "Essay 1", "score": "B+"},
]

FORUM = [
    {
        "id": "t1",
        "course": "CS301",
        "title": "Lab 4: round-robin quantum?",
        "posts": [
            {"author": "Priya S.", "text": "Is the time quantum fixed at 10 ms, or do we choose it?"},
            {
                "author": "Dr. Ines Kovac",
                "text": "Use 10 ms for the graded runs. You may add an experiment with other values.",
            },
        ],
    },
    {
        "id": "t2",
        "course": "MA204",
        "title": "Study group for problem set 5",
        "posts": [
            {"author": "Daniel R.", "text": "Library group room 4, Saturday 14:00. Everyone welcome."},
        ],
    },
]
