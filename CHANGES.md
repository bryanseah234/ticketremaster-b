# Kubernetes Robustness Change Plan

## Goal

Plan the next round of Kubernetes robustness work without implementing it yet. This plan focuses on reducing fragility in the current `k8s/base` manifests while keeping the existing local Docker Desktop cluster limitations explicit.

## Current Fragility

### Platform-level constraint

- The cluster is still a single-node Docker Desktop environment, so a node failure still means total downtime no matter how well pod self-healing works.

### Workload-level gaps

- Many core Deployments in `k8s/base/core-workloads.yaml` are still `replicas: 1`, which means restart recovery exists but true zero-downtime redundancy does not.
- Most workloads rely on readiness and liveness probes only; startup behavior is still fragile for slow boot paths.
- RabbitMQ and Redis recover after restarts but remain single replica, so they are not highly available.
- Resource requests and limits are not broadly defined, so the scheduler and kubelet have less control during CPU and memory pressure.
- PodDisruptionBudgets are not in place, so voluntary disruptions can still fully interrupt singleton or low-replica workloads.

## Planning Principles

- Prioritize the purchase path first.
- Improve stateless services before redesigning stateful HA.
- Keep changes compatible with local Kubernetes validation.
- Separate immediate resilience gains from larger production-grade architecture changes.
- Treat RabbitMQ, Redis, and Postgres HA as a later phase unless managed services are introduced.

## Proposed Execution Plan

### Phase 1: Raise baseline resilience for critical stateless workloads

Target the most important stateless services first in `k8s/base/core-workloads.yaml`:

- `event-orchestrator`
- `ticket-purchase-orchestrator`
- `seat-inventory-service`
- `ticket-service`
- `user-service`

Planned changes:

- Increase these Deployments from 1 replica to 2 replicas.
- Confirm each target remains safe to scale horizontally, especially around startup actions, queue consumers, and any migration assumptions.
- Keep lower-priority workloads at 1 replica initially to avoid unnecessary resource pressure in Docker Desktop.

Why first:

- This is the fastest path to reducing single-pod outage risk for the core user and purchase flows.
- These gains are meaningful even before autoscaling is added.

### Phase 2: Add startup probes where cold-start timing is variable

Primary target:

- RabbitMQ in the data-plane manifests

Secondary targets:

- Flask workloads that can start slowly because they wait on database readiness, migrations, gRPC dependencies, or queue setup

Planned changes:

- Add `startupProbe` to RabbitMQ first.
- Review critical Flask services and orchestrators for slow boot behavior and add `startupProbe` where liveness checks could fire too early.
- Keep existing readiness and liveness probes, but tune startup windows so cold boot does not look like failure.

Why second:

- This reduces false restarts during cluster startup and improves stability under local resource constraints.

### Phase 3: Add resource requests and limits

Primary scope:

- Critical purchase-path services
- RabbitMQ
- Redis
- Remaining core stateless workloads after the critical set is stable

Planned changes:

- Define CPU and memory requests for predictable scheduling.
- Define limits conservatively so Docker Desktop remains usable.
- Start with tighter values for lower-priority services and reserve more headroom for the purchase path.

Why third:

- Replicas and probes improve availability, but requests and limits make those improvements more reliable under contention.

### Phase 4: Add PodDisruptionBudgets

Primary scope:

- Multi-replica critical stateless workloads
- Potentially selected singleton services where voluntary disruption protection is still valuable

Planned changes:

- Create PodDisruptionBudgets for the workloads scaled in Phase 1.
- Use policies that preserve at least one healthy pod during drains and controlled restarts.
- Avoid overly strict budgets that could block maintenance in a small local cluster.

Why fourth:

- PDBs only become more useful once replicas exist.

### Phase 5: Add HorizontalPodAutoscalers

Best candidates:

- `seat-inventory-service`
- `ticket-purchase-orchestrator`

Planned changes:

- Add HPAs after requests are in place, because autoscaling depends on resource signals being meaningful.
- Start with conservative minimum and maximum replica counts suitable for local testing.
- Validate scale behavior under synthetic load without exhausting the single-node environment.

Why fifth:

- HPA before requests and limits usually produces weaker results.

### Phase 6: Plan for multi-node resilience and stronger stateful HA

Future scope:

- Topology spread constraints
- Pod anti-affinity
- Stronger RabbitMQ and Redis HA patterns
- Managed messaging and data services

Planned changes:

- Introduce anti-affinity and topology spread only once the environment has more than one node.
- Revisit RabbitMQ and Redis architecture for real HA rather than simple restart recovery.
- Consider managed RabbitMQ, Redis, and eventually managed Postgres where operationally appropriate.

Why last:

- These changes matter most in multi-node or production-like environments and are not fully testable on single-node Docker Desktop.

## Phase-by-Phase Handoff

### Phase 1 handoff: scale the critical stateless path

Objective:

- Reduce single-pod failure risk on the most important stateless workloads first.

Files to edit:

- `k8s/base/core-workloads.yaml`

Work items:

- Change `replicas` from `1` to `2` for:
  - `event-orchestrator`
  - `ticket-purchase-orchestrator`
  - `seat-inventory-service`
  - `ticket-service`
  - `user-service`
- Leave the remaining Deployments at `1` replica for now unless there is a clear reason to include them in the critical path.
- Verify each selected Deployment is stateless enough to scale without introducing duplicate side effects.
- Specifically review whether any startup logic, queue consumer behavior, or one-time initialization inside these workloads could behave incorrectly when two pods start together.

Definition of done:

- The five target Deployments run at `2` replicas in the rendered manifests.
- No target workload depends on singleton-only behavior.
- The changes remain limited enough for Docker Desktop to handle them.

### Phase 2 handoff: add startup probes

Objective:

- Prevent false restarts during cold boot or dependency-heavy startup.

Files to edit:

- `k8s/base/data-plane.yaml`
- `k8s/base/core-workloads.yaml`

Work items:

- Add a `startupProbe` to `rabbitmq` first.
- Review the critical Flask workloads from Phase 1 and add `startupProbe` where the app may need extra time to become stable.
- Keep existing readiness and liveness probes in place; the goal is not to replace them, but to protect slow-start workloads from premature liveness failure.
- Prefer probe timings that are conservative enough for Docker Desktop cold start, especially when databases, Redis, RabbitMQ, and gRPC dependencies are all starting together.

Definition of done:

- RabbitMQ has a `startupProbe`.
- Every workload identified as slow-starting has a startup window that protects it from unnecessary restarts.
- Readiness and liveness behavior still represent real runtime health after startup completes.

### Phase 3 handoff: add requests and limits

Objective:

- Give the scheduler and kubelet predictable resource boundaries before autoscaling or broader resilience tuning.

Files to edit:

- `k8s/base/core-workloads.yaml`
- `k8s/base/data-plane.yaml`

Work items:

- Add CPU and memory `requests` and `limits` for the Phase 1 critical workloads.
- Add CPU and memory `requests` and `limits` for `rabbitmq` and `redis`.
- Add resource settings to the remaining core Deployments only after the critical set is covered.
- Keep the values conservative enough for a single-node local cluster, but bias more headroom toward the purchase path than lower-priority services.
- Avoid values that would cause the cluster to become unschedulable during normal local bring-up.

Definition of done:

- Critical stateless workloads, RabbitMQ, and Redis all have explicit resource requests and limits.
- The local cluster can still schedule and run the full stack.
- Resource settings make future HPA behavior meaningful.

### Phase 4 handoff: add PodDisruptionBudgets

Objective:

- Preserve service availability during voluntary disruptions such as drains, restarts, and upgrades.

Files to edit:

- Add a new manifest file under `k8s/base/` for PodDisruptionBudgets
- `k8s/base/kustomization.yaml`

Work items:

- Create PodDisruptionBudgets for the workloads scaled to `2` replicas in Phase 1.
- Use policies that preserve at least one available pod during voluntary disruption.
- Avoid creating budgets that are too strict for a small local cluster.
- Update `kustomization.yaml` so the new PDB manifest is included in the base render.

Definition of done:

- Critical multi-replica workloads have PodDisruptionBudgets.
- The PDB policies protect availability without blocking ordinary local operations.
- The base kustomization includes the new manifest.

### Phase 5 handoff: add HorizontalPodAutoscalers

Objective:

- Add controlled elasticity to the workloads most likely to need scaling under traffic bursts.

Files to edit:

- Add a new manifest file under `k8s/base/` for HPAs
- `k8s/base/kustomization.yaml`

Priority targets:

- `seat-inventory-service`
- `ticket-purchase-orchestrator`

Work items:

- Add HorizontalPodAutoscalers only after Phase 3 is complete.
- Start with conservative min/max replica ranges suitable for Docker Desktop.
- Use CPU-based scaling first unless there is already a stronger signal available in the manifests or metrics setup.
- Update `kustomization.yaml` so the HPA manifest is included.

Definition of done:

- The two priority workloads have HPAs.
- Autoscaling inputs are based on real resource requests rather than default zero-baseline behavior.
- The HPA settings do not overwhelm local cluster capacity.

### Phase 6 handoff: plan the real HA transition

Objective:

- Move from improved pod-level resilience to real infrastructure-level resilience once the environment supports it.

Files likely to change later:

- `k8s/base/core-workloads.yaml`
- `k8s/base/data-plane.yaml`
- `k8s/base/kustomization.yaml`
- Additional manifests for scheduling constraints or stateful HA patterns

Work items:

- Add pod anti-affinity and topology spread constraints only when the cluster has more than one node.
- Reassess RabbitMQ and Redis architecture, since single-replica StatefulSets are restart-resilient but not truly highly available.
- Consider whether RabbitMQ, Redis, and eventually Postgres should move to managed services instead of self-managed HA in-cluster.
- Treat this phase as a topology upgrade, not just a YAML tuning pass.

Definition of done:

- Replicas can survive node-level failure because workloads are distributed across nodes.
- RabbitMQ and Redis no longer represent single-instance availability bottlenecks.
- Stateful HA decisions are aligned with the target runtime environment, not just local Docker Desktop.

## File-Level Implementation Map

- `k8s/base/core-workloads.yaml`
  - Scale critical stateless Deployments
  - Add startup probes to selected Flask workloads
  - Add resource requests and limits

- `k8s/base/data-plane.yaml`
  - Add startup probe to RabbitMQ
  - Add resource requests and limits to RabbitMQ and Redis
  - Reassess whether current single-replica stateful patterns should remain explicitly temporary

- `k8s/base/kustomization.yaml`
  - Include any new manifests created for PodDisruptionBudgets or HPAs

- New manifests likely required later
  - PodDisruptionBudget definitions
  - HorizontalPodAutoscaler definitions

## Recommended Priority

### Tier 1

- Scale critical stateless services to 2 replicas
- Add startup probes where boot time is variable
- Add resource requests and limits

### Tier 2

- Add PodDisruptionBudgets
- Add HPAs

### Tier 3

- Move RabbitMQ and Redis toward stronger HA or managed patterns
- Add anti-affinity and topology spread when running on multi-node infrastructure

## Validation Plan Once Implementation Starts

- Render manifests with `kubectl kustomize k8s/base`.
- Apply to the cluster and verify rollouts complete cleanly.
- Confirm critical Services stay reachable during single-pod deletion tests.
- Confirm startup probes prevent premature restarts during cold cluster boot.
- Confirm resource settings do not overload Docker Desktop capacity.
- Confirm HPAs react only after requests and limits are in place.

## Expected Outcome

After Phases 1 through 5, the platform should be materially more resilient to pod failure, startup timing issues, and resource contention. It will still not be fully highly available until it runs on multiple nodes and the stateful dependencies move beyond single-replica patterns.
