Feature: Analysis pipeline
    The analysis pipeline transforms raw post and comment data
    into structured markdown analysis reports.

    Scenario: Empty account produces minimal output
        Given zero posts and zero comments
        When analysis markdown is generated for "@emptyuser"
        Then the markdown contains "Account Analysis"
        And the markdown contains "0 scraped posts"
        And the markdown contains "No posts were returned"

    Scenario: Account with posts and comments produces full report
        Given 3 posts with captions and 2 comments
        When analysis markdown is generated for "@activeuser"
        Then the markdown contains "Account Analysis"
        And the markdown contains "Pattern Observations"
        And the markdown contains "Swipe-Worthy Posts"
        And the markdown contains "Strategy Implications"
        And the markdown contains "3 scraped posts"

    Scenario: Hashtags and mentions are extracted from captions
        Given a post with caption "Love #python and @friend"
        When analysis markdown is generated for "@taguser"
        Then the markdown contains "#python"
        And the markdown contains "@friend"
