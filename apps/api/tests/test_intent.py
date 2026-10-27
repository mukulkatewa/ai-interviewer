import pytest

from app.interview.intent import wants_to_stop


@pytest.mark.parametrize(
    "text",
    [
        "I want to stop the interview.",
        "Can we end the interview please?",
        "Please stop the interview now",
        "Let's finish this interview",
        "Stop.",
        "stop please",
        "Okay, stop.",
        "End interview",
        "Enough.",
        "I'm done.",
        "That's all, thank you.",
        "Let's stop here.",
        "Can we wrap up?",
        "Sorry, I need to go.",
        "I have to leave now",
        "I want to quit",
        "I’m done now",  # curly apostrophe, as speech-to-text often writes it
    ],
)
def test_real_requests_to_stop(text):
    assert wants_to_stop(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "We stop the container before deleting the volume.",
        "I would stop the server, run the migration and restart it.",
        "Stop words are removed in the preprocessing step of the pipeline.",
        "I'm done with the migration, and then I deploy it to staging.",
        "I need to go through the logs to find the root cause.",
        "We end the session when the token expires.",
        "The end of the interview process is when HR sends feedback.",
        "I enjoyed the interview process at my last company.",
        "That's all handled by the load balancer, which retries failed requests.",
        "I want to stop memory leaks by closing the connections explicitly.",
        "Let's finish the rollout in two phases, starting with five percent of traffic.",
        # Short enough to pass the word cap, and they START with a command: only the
        # "must end right after the command" rule keeps these from ending the interview.
        "Stop words are removed early.",
        "I'm done with the migration.",
        "I need to go through the logs.",
        "End users never see this error.",
        "Finish the migration before deploying.",
        "Enough memory is allocated per pod.",
        "Quit the process gracefully on SIGTERM.",
    ],
)
def test_technical_answers_never_end_the_interview(text):
    assert not wants_to_stop(text)
