# Kourovka Notebook Problem 17.91

These paired one-hour experiments compare Albilich with CAS work modes enabled
and globally disabled on the same target: determine whether a finite soluble
group can have a maximal subgroup whose derived length is smaller by four.

Neither run solved the root problem. Both produced certified partial progress,
but they explored materially different proof routes. The CAS-on run developed
and checked augmentation-ideal and split-lift certificates. The CAS-off run
developed structural reductions around the core of a least counterexample.

- [CAS-on run](cas-on-1h/)
- [CAS-off run](cas-off-1h/)

The two reports must not be interpreted as a controlled causal comparison:
their prompts and search settings were not identical, and the CAS-on prompt
included prior-corpus constraints that the fresh CAS-off statement did not.
