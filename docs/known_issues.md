# Known Issues

This log tracks product and system issues that are known but not yet fixed.

## KI-001: Multi-agent requests are handled by only one routed sub-agent

**Status:** Open  
**Area:** Agent orchestration / multi-agent routing  
**Reported:** 2026-06-03  
**Severity:** Medium  

### Summary

When a user asks for a compound action that spans more than one specialist agent, the coordinator appears to route the full request to a single sub-agent. The selected sub-agent performs only the part it owns, then its response flows directly back to the user instead of the coordinator decomposing the request, delegating subtasks, and synthesizing a combined response.

### Reproduction

Ask Kitch:

```text
clear the meal plan and grocery cart
```

Reported response:

```text
I cleared the planned grocery cart rows.

I can’t clear the weekly meal plan from here — that’s handled by the meal planning agent.
```

Then ask:

```text
clear the meal plan
```

The meal plan clears successfully.

### Expected Behavior

The coordinator should recognize the request as a compound task:

1. Clear the meal plan using the meal-planning capability.
2. Clear the grocery cart using the grocery-cart capability.
3. Return one final response summarizing both outcomes.

### Observed Behavior

The system behaves more like single-agent routing than task decomposition:

1. The full user request is sent to one specialist.
2. That specialist completes only its own part.
3. The specialist declines the other part instead of handing control back to the coordinator.
4. The specialist response is returned directly to the user.

### Suspected Cause

The parent orchestrator likely chooses a single sub-agent for the whole user message and does not currently break compound intents into separate subtasks. The response contract also appears to allow a sub-agent's partial/limitation response to surface directly without coordinator-level aggregation.

### Impact

- Multi-intent household operations feel unreliable.
- Users may need to repeat themselves for each specialist domain.
- The agent can expose internal boundaries such as "handled by another agent," which makes the system feel less cohesive.

### Notes

- Do not fix yet.
- This should be evaluated as an orchestration design issue, not as a missing meal-plan tool issue, because the single-intent meal-plan clear flow works.
