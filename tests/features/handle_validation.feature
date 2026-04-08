Feature: Handle validation
    Validate Instagram handle cleaning and normalization.

    Scenario Outline: Valid handles are normalized correctly
        When cleaning handle "<input>"
        Then the result is "<expected>"

        Examples:
            | input      | expected  |
            | @testuser  | testuser  |
            | testuser   | testuser  |
            | @@test     | test      |

    Scenario: Empty handle raises validation error
        When cleaning handle ""
        Then a ValueError is raised

    Scenario: Whitespace-only handle raises validation error
        When cleaning handle "   "
        Then a ValueError is raised
