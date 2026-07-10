FROM ghcr.io/tempoxyz/tempo-bench-base:v1

# These documentation-only tasks do not use the on-chain verifier. Remove its
# Tempo SDK sources so they cannot become an unintended research corpus.
RUN rm -rf /opt/tempo-bench/verifier /opt/tempo-bench-rewardkit
