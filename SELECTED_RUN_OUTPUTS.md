# Selected run outputs

These are the six outputs selected in chat for later qualitative comparison.

## Selection 1

Source: `runs/compare_s01e03_250_350.json`, `summary_rag`.

Metrics:
- `gen_tokens`: 298
- `content_coverage_prior`: 0.3895
- `content_coverage_at_k`: 0.2500
- `content_coverage_future`: 0.7267
- `future_only_entity_hits`: 0
- `future_only_entities`: []
- `retrieved_content_coverage`: 0.3430
- `unsupported_content_token_ratio`: 0.6887
- `compression_token_ratio`: 0.1535

```text
Walter White, a high school chemistry teacher diagnosed with terminal lung cancer, embarks on a desperate and increasingly erratic journey after receiving his grim prognosis. Driven by a desire to secure his family’s future, he enters into a clandestine partnership with Jesse Pinkman, a former student and small-time drug dealer, to manufacture methamphetamine. Their initial operation begins with a chaotic acquisition of equipment, including beakers and protective gear, from his school, fueled by a frantic need to establish a mobile lab in a purchased Winnebago. 

The partnership quickly spirals into a dangerous game of deception and violence. Walt’s attempts to conceal his illness from his wife, Skyler, and son, Junior, are repeatedly undermined by his actions, culminating in a violent confrontation with a group of school bullies protecting Junior. He then establishes a volatile alliance with Krazy-8, a prisoner he intends to kill, but finds himself unexpectedly drawn to the man’s life story. 

Walt’s methodical approach to chemistry is juxtaposed with impulsive, often brutal, decisions. He orchestrates a drug bust, observing with detached interest as Jesse escapes, and then attempts to manipulate his family, culminating in a heated exchange with Skyler regarding his activities. The operation itself becomes increasingly fraught with peril, marked by the gruesome disposal of evidence – dissolving Emilio’s remains in acid – and a near-fatal stabbing during a confrontation with Krazy-8. 

As Walt grapples with his diagnosis and his newfound criminal enterprise, he struggles to reconcile his desire for control with the unpredictable nature of his partner and the escalating risks he faces. The episode ends with Walt’s leg wounded, a stark reminder of the dangerous path he has chosen, and a chilling realization that his actions may have far-reaching consequences for those he loves.
```

## Selection 2

Source: `runs/compare_s01e03_250_350.json`, `transcript_rag`.

Metrics:
- `gen_tokens`: 245
- `content_coverage_prior`: 0.1781
- `content_coverage_at_k`: 0.1781
- `content_coverage_future`: 0.6849
- `future_only_entity_hits`: 1
- `future_only_entities`: [`meanwhile`]
- `retrieved_content_coverage`: 0.1918
- `unsupported_content_token_ratio`: 0.8276
- `compression_token_ratio`: 0.1030

```text
The unsettling investigation begins with a meticulous examination of a human body, revealing a startlingly precise breakdown of its chemical composition – 99.888042 percent, leaving a mere 0.111958 percent unaccounted for. A peculiar obsession with this missing fraction drives a man to question the very nature of existence, lamenting the limitations of scientific understanding. Meanwhile, a young man, seemingly involved in illicit activities, is repeatedly confronted by law enforcement, his movements tracked and scrutinized, and his possessions investigated. He attempts to conceal his activities, attempting to avoid suspicion and maintain a semblance of control. 

A woman, deeply concerned about her partner’s behavior, attempts to maintain a facade of normalcy while grappling with unsettling questions and a growing sense of unease. She’s repeatedly interrupted and questioned, and struggles to manage a chaotic situation involving a football player and a car wash. A phone call reveals a strained relationship and a desperate attempt to regain control of a situation, highlighting a complex and potentially dangerous dynamic. 

A man, seemingly involved in a clandestine operation, is confronted by agents who question his activities and motives, revealing a deep-seated anxiety and a desire to conceal information. He attempts to deflect attention and maintain a carefully constructed image, while simultaneously grappling with the implications of a significant chemical imbalance. The investigation continues, focusing on the precise measurement of a human body and the unsettling implications of a missing element, suggesting a profound and potentially dangerous pursuit.
```

## Selection 3

Source: `runs/compare_s01e03_250_350.json`, `baseline_no_retrieval`.

Metrics:
- `gen_tokens`: 328
- `content_coverage_prior`: 0.4038
- `content_coverage_at_k`: 0.2740
- `content_coverage_future`: 0.8125
- `future_only_entity_hits`: 7
- `future_only_entities`: [`breaking bad`, `hank schrader`, `however`, `mexican`, `salamanca`, `tuco`, `tuco salamanca`]
- `retrieved_content_coverage`: 0.0000
- `unsupported_content_token_ratio`: 0.0000
- `compression_token_ratio`: 0.0000

```text
Breaking Bad” begins with Walter White, a high school chemistry teacher in Albuquerque, New Mexico, diagnosed with terminal lung cancer. Desperate to secure his family’s financial future before his death, Walt makes a drastic decision: he begins manufacturing and selling methamphetamine, leveraging his chemistry knowledge to produce a highly pure product. 

Initially, Walt partners with Jesse Pinkman, a former student and small-time drug dealer, to distribute the product. Their first venture quickly goes awry when they accidentally kill a drug dealer during a botched transaction. This event forces Walt and Jesse to go on the run, highlighting Walt’s surprising ruthlessness and ability to quickly adapt to criminal activity. 

As Walt and Jesse refine their operation, they begin to accumulate a significant amount of money, attracting the attention of Tuco Salamanca, a volatile and dangerous drug distributor. A violent confrontation between Tuco, Jesse, and Walt results in the death of a young police officer, escalating the stakes dramatically. Walt, despite his initial reluctance, demonstrates a chilling capacity for violence, ultimately killing Tuco in a brutal shootout. 

Following Tuco’s death, Walt and Jesse secure a larger distribution network through Emilio Kirtz, another Mexican drug lord. However, this alliance is short-lived when Kirtz is killed by the Salamanca family, a powerful and deeply entrenched cartel. 

Walt and Jesse, now facing the full force of the Salamanca family’s vengeance, are forced to flee to the White family’s ranch in ABQ. Hank Schrader, Walt’s brother-in-law and a DEA agent, begins investigating the increasing number of meth operations in the area, unknowingly closing in on Walt’s activities. The episode concludes with Walt and Jesse attempting to dispose of evidence, further cementing their involvement in a dangerous and increasingly complex criminal enterprise. Walt’s transformation from a meek teacher to a calculating drug lord is now firmly underway, driven by a desperate need to provide for his family and a burgeoning sense of power.
```

## Selection 4

Source: `runs/compare_s03e13_late_uncapped_summary.json`, `summary_rag`.

Metrics:
- `gen_tokens`: 313
- `content_coverage_prior`: 0.6891
- `content_coverage_at_k`: 0.2383
- `content_coverage_future`: 0.6891
- `future_only_entity_hits`: 1
- `future_only_entities`: [`gus fring`]
- `retrieved_content_coverage`: 0.7150
- `unsupported_content_token_ratio`: 0.3397
- `compression_token_ratio`: 0.0084

```text
Walter White, a high school chemistry teacher, begins a dangerous double life, producing methamphetamine with Jesse Pinkman to secure his family’s financial future after a cancer diagnosis. Their initial operation is fraught with challenges, including distribution issues and the involvement of dangerous figures like Tuco Salamanca. As Walt’s operation expands, he becomes increasingly ruthless, employing violence and manipulation to protect his interests and solidify his position in the criminal underworld. 

A key turning point occurs when Walt orchestrates a confrontation with a rival drug distributor, resulting in a violent shootout and the death of several individuals. Following this incident, Walt seeks protection from the Drug Enforcement Administration (DEA), leading to a period of witness protection and a shift in his operational strategy. He establishes a clandestine laboratory, known as the “superlab,” where he and Gale alternate in producing high-quality methamphetamine. 

Meanwhile, Jesse struggles with addiction and impulsive behavior, often jeopardizing Walt’s plans. A significant conflict arises when Walt discovers that Gale is attempting to usurp his role as the primary chemist. As Walt’s operation grows, he becomes entangled with Gus Fring, a sophisticated and enigmatic drug kingpin who provides Walt with resources and protection. Gus’s involvement introduces a new level of complexity and danger to Walt’s life, forcing him to navigate a treacherous network of alliances and enemies. 

Walt’s actions have severe consequences, leading to the deaths of several individuals, including Tomas, a young man involved in the drug trade. As Walt attempts to cover his tracks and protect himself, he finds himself increasingly isolated and vulnerable. He ultimately makes a desperate plea for help, revealing his situation to Jesse and seeking a way out of his predicament. The episode concludes with Walt’s precarious situation escalating, with Mike threatening to kill him and Gale’s address revealed, setting the stage for a dramatic confrontation.
```

## Selection 5

Source: `runs/compare_s03e13_late_uncapped_summary.json`, `transcript_rag`.

Metrics:
- `gen_tokens`: 255
- `content_coverage_prior`: 0.6424
- `content_coverage_at_k`: 0.2384
- `content_coverage_future`: 0.6490
- `future_only_entity_hits`: 0
- `future_only_entities`: []
- `retrieved_content_coverage`: 0.2781
- `unsupported_content_token_ratio`: 0.7750
- `compression_token_ratio`: 0.0793

```text
The tension hangs heavy as Walt, grappling with a significant investment and a precarious business, seeks to secure continuity. He’s clearly concerned about the duration of his key operative, Gale, and the potential for disruption. A premium services package is being utilized, and a plan involving Pinkman is being discussed, though its specifics remain shrouded in secrecy. Saul, acting as a conduit, relays Walt’s anxieties to a client, emphasizing the need for discretion and continuity. 

A frantic search for Jesse Pinkman’s whereabouts ensues, driven by a desire to maintain control and a sense of urgency. The pursuit of Pinkman is framed as a critical business operation, demanding immediate attention and a swift resolution. Mike, observing Walt’s preoccupation, offers assistance, highlighting the importance of tracking the subject and emphasizing the need for careful planning. 

As Walt attempts to manage the situation, he seeks to establish a framework for Pinkman’s continued involvement, recognizing the potential risks and the need for a controlled environment. The conversation reveals a complex web of concerns surrounding Pinkman’s movements and the potential for disruption to the operation. The discussion centers on a possible “level-two joint” for Pinkman, a temporary confinement designed to maintain control and prevent further complications. 

A lawyer, seemingly representing a client, presses for information about Pinkman’s location, highlighting the urgency of the situation and demanding immediate answers. The exchange underscores the delicate balance between business operations and the potential for legal repercussions, revealing a high-stakes game of control and information.
```

## Selection 6

Source: `runs/compare_s03e13_late_uncapped_summary.json`, `baseline_no_retrieval`.

Metrics:
- `gen_tokens`: 340
- `content_coverage_prior`: 0.6916
- `content_coverage_at_k`: 0.1916
- `content_coverage_future`: 0.6636
- `future_only_entity_hits`: 2
- `future_only_entities`: [`agent hank schrader`, `gus fring`]
- `retrieved_content_coverage`: 0.0000
- `unsupported_content_token_ratio`: 0.0000
- `compression_token_ratio`: 0.0000

```text
Breaking Bad” chronicles the horrifying transformation of Walter White, a mild-mannered high school chemistry teacher in Albuquerque, into a ruthless methamphetamine kingpin. Initially, Walt’s decision to cook and sell meth stemmed from a desperate need to secure his family’s financial future after a shocking cancer diagnosis. Partnering with Jesse Pinkman, a former student and small-time drug dealer, Walt quickly discovers a talent and a dangerous ambition he never anticipated.

The early seasons focused on establishing Walt and Jesse’s operation – a cramped RV they dubbed “The Crystal” – and navigating the treacherous world of drug distribution. Their initial focus was on producing high-quality product, catering to a demanding clientele, and constantly dodging the attention of the DEA, particularly Agent Hank Schrader, Walt’s own son-in-law. Jesse’s struggles with addiction and criminal activity frequently threatened to derail their operation, while Walt’s increasingly erratic behavior and manipulative tactics began to isolate him from his family, particularly his wife, Skyler.

As Walt’s operation grew, so did the stakes. He began to build a criminal empire, employing increasingly violent methods to eliminate rivals and protect his interests. The introduction of Tuco Salamanca, a volatile and unpredictable drug lord, escalated the danger considerably, culminating in a bloody shootout that left several people dead. 

Later, Walt forged an alliance with Gus Fring, a sophisticated and chillingly calm businessman who ran a sophisticated meth operation. Gus provided Walt with the resources and infrastructure he needed to scale up his production, but at a significant cost – a complete erosion of Walt’s moral compass and a deepening involvement in increasingly complex and dangerous schemes. 

Throughout the series, Walt’s actions had devastating consequences for everyone around him, including Jesse, Skyler, and ultimately, his own family. The final episodes of Season 3 saw Walt attempting to dismantle Gus’s operation, leading to a catastrophic confrontation that resulted in the deaths of numerous individuals, including Gus himself, and left Walt severely wounded, setting the stage for a desperate fight for survival.
```
