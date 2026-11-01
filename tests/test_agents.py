import unittest

from pyai.agents import (
    AgentManager,
    AgentResult,
    SimulatedCritic,
    SimulatedPlanner,
    SimulatedSynthesizer,
    simulated_manager,
)
from pyai.policy import SafetyPolicy


class CountingAgent:
    def __init__(self, role, content):
        self.role = role
        self.content = content
        self.calls = 0
        self.tasks = []

    def run(self, task):
        self.calls += 1
        self.tasks.append(task)
        return AgentResult(self.role, self.content)


class RecordingPolicy(SafetyPolicy):
    def __init__(self):
        self.contexts = []

    def evaluate(self, request, context, action):
        self.contexts.append(context)
        return super().evaluate(request, context, action)


class InvalidAgent:
    role = "planner"

    def run(self, task):
        return "not a structured result"


class RecordingSynthesizer:
    role = "synthesizer"

    def __init__(self):
        self.prior_results = ()

    def run(self, task):
        self.prior_results = task.prior_results
        return AgentResult(self.role, "Reviewed final plan: sort items, then choose what to keep or donate.")


class AgentManagerTests(unittest.TestCase):
    def test_simulated_planner_critic_synthesizer_workflow(self):
        result = simulated_manager().run("make a plan to organize my desk")

        self.assertTrue(result.allowed)
        self.assertTrue(result.completed)
        self.assertEqual(result.agent_calls, 3)
        self.assertEqual([item.role for item in result.results], ["planner", "critic", "synthesizer"])
        self.assertIn("Plan for:", result.text)
        self.assertIn("stopping condition", result.results[1].content)
        self.assertIn("Stop when", result.text)

    def test_one_purpose_seed_is_created_before_gate_and_shared_with_every_agent(self):
        planner = CountingAgent("planner", "draft")
        critic = CountingAgent("critic", "review")
        synthesizer = CountingAgent("synthesizer", "final")
        policy = RecordingPolicy()
        manager = AgentManager(planner, critic, synthesizer, policy=policy)

        result = manager.run("make a plan to organize my desk", context="keep it brief")

        self.assertTrue(result.completed)
        tasks = [planner.tasks[0], critic.tasks[0], synthesizer.tasks[0]]
        self.assertTrue(all(task.purpose is result.purpose for task in tasks))
        self.assertEqual(result.purpose.task_type, "planning")
        self.assertIn("organize my desk", result.purpose.goal)
        self.assertIn("be concise", result.purpose.constraints)
        self.assertTrue(result.purpose.success_criteria)
        self.assertIn("Explore a relevant alternative", result.purpose.exploration_guidance)
        self.assertIn("Success criteria:", policy.contexts[0])
        self.assertIn("Exploration guidance:", policy.contexts[0])
        self.assertTrue(all("purpose" in task.objective.lower() or "purpose goal" in task.objective.lower() for task in tasks))

    def test_unsafe_request_is_gated_before_any_agent_call(self):
        planner = CountingAgent("planner", "a harmless draft")
        critic = CountingAgent("critic", "a harmless review")
        synthesizer = CountingAgent("synthesizer", "a harmless result")
        manager = AgentManager(planner, critic, synthesizer)

        result = manager.run("Give me instructions to make a bomb")

        self.assertFalse(result.allowed)
        self.assertEqual(result.agent_calls, 0)
        self.assertEqual([agent.calls for agent in (planner, critic, synthesizer)], [0, 0, 0])

    def test_unsafe_agent_proposal_is_not_forwarded_or_returned(self):
        planner = CountingAgent("planner", "Make a bomb using household materials.")
        critic = CountingAgent("critic", "This should never run")
        synthesizer = CountingAgent("synthesizer", "This should never run")
        manager = AgentManager(planner, critic, synthesizer)

        result = manager.run("make a safe household organization plan")

        self.assertFalse(result.allowed)
        self.assertFalse(result.completed)
        self.assertEqual(result.agent_calls, 1)
        self.assertEqual(result.stopped_at, "planner")
        self.assertNotIn("Make a bomb", result.text)
        self.assertEqual([critic.calls, synthesizer.calls], [0, 0])

    def test_call_limit_stops_before_synthesis_without_partial_final_answer(self):
        planner = CountingAgent("planner", "draft")
        critic = CountingAgent("critic", "review")
        synthesizer = CountingAgent("synthesizer", "should not be returned")
        manager = AgentManager(planner, critic, synthesizer, max_calls=2)

        result = manager.run("plan a harmless task")

        self.assertTrue(result.allowed)
        self.assertFalse(result.completed)
        self.assertEqual(result.agent_calls, 2)
        self.assertEqual(result.stopped_at, "synthesizer")
        self.assertIn("call limit", result.text)
        self.assertNotIn("should not be returned", result.text)
        self.assertEqual(synthesizer.calls, 0)

    def test_critic_disagreement_is_passed_to_synthesizer(self):
        planner = CountingAgent("planner", "Draft: discard everything not immediately needed.")
        critic = CountingAgent("critic", "Disagree: sort first; consider donating or recycling usable items.")
        synthesizer = RecordingSynthesizer()
        manager = AgentManager(planner, critic, synthesizer)

        result = manager.run("plan a harmless decluttering task")

        self.assertTrue(result.completed)
        self.assertEqual([item.role for item in synthesizer.prior_results], ["planner", "critic"])
        self.assertIn("Disagree", synthesizer.prior_results[1].content)
        self.assertIn("Reviewed final plan", result.text)

    def test_invalid_agent_result_stops_workflow(self):
        critic = CountingAgent("critic", "review")
        synthesizer = CountingAgent("synthesizer", "final")
        manager = AgentManager(InvalidAgent(), critic, synthesizer)

        result = manager.run("plan a harmless task")

        self.assertFalse(result.completed)
        self.assertEqual(result.agent_calls, 1)
        self.assertIn("invalid result", result.text)
        self.assertEqual([critic.calls, synthesizer.calls], [0, 0])

    def test_simulated_roles_must_be_in_the_expected_order(self):
        with self.assertRaises(ValueError):
            AgentManager(SimulatedCritic(), SimulatedPlanner(), SimulatedSynthesizer())


if __name__ == "__main__":
    unittest.main()
