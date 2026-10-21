"""Offline robots regressions; never access a real municipal page."""
import unittest
from hamar_agent.robots_policy import robots_interval


class RobotsPolicyTests(unittest.TestCase):
    def check(self, policy, path="/water/", agent="HamarKommuneAgent/0.2"):
        return robots_interval(policy.encode(), "https://www.hamar.kommune.no" + path, agent)

    def test_specific_disallow_overrides_empty_disallow_and_allow_root(self):
        policy = "User-agent: *\nDisallow: \nAllow: /\nCrawl-delay: 5\nDisallow: /sok/"
        self.assertEqual(self.check(policy), 5)
        with self.assertRaises(ValueError):self.check(policy, "/sok/")

    def test_longest_path_allow_wins_and_order_does_not_matter(self):
        self.assertEqual(self.check("User-agent: *\nDisallow: /\nAllow: /water/"), 2)
        self.assertEqual(self.check("User-agent: *\nAllow: /water/\nDisallow: /"), 2)

    def test_allow_wins_equal_specificity(self):
        self.assertEqual(self.check("User-agent: *\nDisallow: /water/\nAllow: /water/"), 2)

    def test_specific_agent_groups_and_combined_groups(self):
        policy = "User-agent: *\nDisallow: /\nUser-agent: HamarKommuneAgent\nAllow: /\nCrawl-delay: 5\nUser-agent: HamarKommuneAgent\nDisallow: /private/\nRequest-rate: 1/10"
        self.assertEqual(self.check(policy), 10)
        with self.assertRaises(ValueError):self.check(policy, "/private/")
        with self.assertRaises(ValueError):self.check(policy, agent="Other")

    def test_wildcard_and_end_anchor(self):
        policy="User-agent: *\nDisallow: /*.pdf$"
        with self.assertRaises(ValueError):self.check(policy, "/folder/file.pdf")
        self.assertEqual(self.check(policy, "/folder/file.pdf/more"), 2)

    def test_encoded_unreserved_equivalence(self):
        with self.assertRaises(ValueError):self.check("User-agent: *\nDisallow: /wat%65r/", "/water/")

    def test_invalid_delays_rates_and_directives_fail_closed(self):
        for directive in ("Crawl-delay: nan", "Crawl-delay: -1", "Crawl-delay: 61", "Request-rate: 0/1", "Request-rate: invalid", "Disallow: relative", "badline"):
            with self.subTest(directive=directive),self.assertRaises(ValueError):self.check("User-agent: *\n"+directive)

    def test_unrelated_agent_does_not_block_our_agent(self):
        self.assertEqual(self.check("User-agent: ClaudeBot\nDisallow: /\nUser-agent: *\nAllow: /\nCrawl-delay: 5"),5)
