# Reviving Legacy IoT Devices as Embodied AI Interfaces: A Software-Only Approach to Sustainable Human-AI Interaction

## Abstract

The recent emergence of large language models (LLMs) has reignited interest in conversational interfaces, yet most interactions remain confined to screens or voice-only assistants. In this paper, we revisit a largely overlooked paradigm: embodied, expressive IoT devices as ambient interfaces for human-AI interaction.

We present a software-only reactivation of the Nabaztag, an early 2000s connected object designed to convey information through motion, light, and sound. Rather than modifying hardware, we demonstrate how modern LLMs can be integrated into legacy devices through a client-server architecture, enabling expressive multimodal behaviors combining speech, physical gestures through ear movement, and light signals.

We introduce the concept of structured expressive generation, where language models produce coordinated multimodal outputs instead of plain text. This approach allows devices to exhibit distinct personalities, emotional expressivity, and contextual reactivity within a constrained physical interface.

Beyond interaction design, our work highlights a novel Green IT strategy: extending the functional lifespan of existing hardware through software augmentation rather than replacement. We argue that legacy devices can become relevant again as embodied AI agents, offering a sustainable alternative to the proliferation of new smart devices.

Through system design, implementation, and exploratory use cases, we discuss the implications of embodied AI for domestic environments, the role of personality in human-device relationships, and the potential of software-defined reconditioning as a paradigm for sustainable innovation.

## Keywords

Embodied AI, Human-AI interaction, Tangible interfaces, Legacy IoT, Green IT, Sustainable HCI, Nabaztag, Expressive agents

## 1. Introduction

Contemporary human-AI interaction is dominated by two interface forms: screens and voice-only assistants. While these forms have proven scalable and convenient, they also narrow the expressive bandwidth of interaction. A text box or a speaker can deliver content efficiently, but they do not necessarily create presence. By contrast, earlier generations of connected objects sometimes explored more situated and embodied interaction models. Among them, the Nabaztag stands out as a particularly compelling case.

Released in the mid-2000s, the Nabaztag was an ambient connected rabbit able to communicate through speech, colored light, and ear movement. Long before the current wave of generative AI, it proposed an alternative vision of digital presence in the home: not an application to open, but a physical companion inhabiting domestic space. Although technically limited by the standards of its time, the device embodied a design intuition that now deserves renewed attention. It suggested that computation could be ambient, expressive, and affectively legible.

This paper argues that legacy connected objects such as the Nabaztag can be reactivated as relevant interfaces for contemporary AI, not through hardware redesign, but through software augmentation alone. This proposition matters for three reasons.

First, it expands the design space of human-AI interaction. Instead of treating generative AI as a purely verbal or visual medium, it frames AI output as coordinated multimodal expression distributed across speech, movement, and lighting.

Second, it reopens the question of embodied domestic agents. The home remains a key site of AI deployment, yet most current devices are designed either as utilitarian speakers or as screen-centric hubs. The Nabaztag offers a different model: a small, characterful, legible object able to communicate affect and intent through nonverbal cues.

Third, it provides a concrete Green IT pathway. Rather than building new AI hardware, we show that an existing object can gain new functionality, renewed relevance, and richer interaction quality through a software-defined stack. In this sense, the project is not only about nostalgic reuse; it proposes a sustainable model for extending the life of legacy devices.

Our contribution is threefold:

1. We describe a software-only architecture for connecting modern LLM and TTS capabilities to a legacy embodied IoT device.
2. We formalize structured expressive generation, a generation paradigm in which the model outputs a multimodal action specification rather than plain text alone.
3. We discuss the design and sustainability implications of turning a legacy device into an embodied AI companion for the domestic environment.

## 2. Background and Motivation

The recent success of LLMs has led to rapid experimentation in digital assistants, copilots, and chat interfaces. However, the interface layer surrounding these models has remained relatively conservative. Most systems still rely on chat windows, smart speakers, or mobile applications. This limitation is not only aesthetic. It shapes the perceived role of AI as either an information service or a productivity tool.

By contrast, embodied interactive objects can communicate intention, mood, and salience through simple but powerful channels: posture, movement, rhythm, color, and voice. Such channels are especially important in domestic settings, where interaction is intermittent, peripheral, and often shared among multiple people.

The Nabaztag is a useful case because it was originally designed around exactly these expressive channels. It already possesses:

- a recognizable body form
- movable ears
- controllable light zones
- audio playback capabilities
- a strong cultural identity as a playful domestic object

These characteristics make it particularly suitable for reactivation as an embodied AI interface. Importantly, the goal is not to retrofit the object materially, but to reinterpret its original affordances through a contemporary software stack.

## 3. System Overview

The system is implemented as a client-server architecture preserving the original role separation between the physical rabbit and the service logic.

At a high level, the system contains:

- a Flask portal for user accounts, rabbit management, and AI configuration
- a FastAPI backend exposing device actions and state
- protocol adapters compatible with Nabaztag-era communication flows
- a modern LLM layer for response and performance generation
- a TTS layer for speech synthesis

Each rabbit can be configured with:

- a personality prompt
- a selected LLM model
- a selected TTS voice
- randomized intervention parameters
- recent conversational memory

This architecture has an important consequence: the rabbit itself does not need to be materially modified to gain access to modern AI behavior. The hardware remains unchanged. The server evolves; the object gains new expressive capacity.

## 4. Structured Expressive Generation

The core conceptual contribution of the project is what we call structured expressive generation.

Traditional conversational systems ask a model to return a textual response. In our system, the model is instead prompted to produce a structured specification describing several coordinated output modalities. A typical response contains:

- a text field to be spoken aloud
- an action for the left ear
- an action for the right ear
- a state for each LED zone, including color or blink pattern

This representation changes the role of the model. It is no longer merely a language generator; it becomes a micro-director of embodied expression. The generated utterance is paired with a posture and a visual state. As a result, the rabbit can signal curiosity, irony, excitement, hesitation, or calm not only through words but through synchronized nonverbal behavior.

This is especially valuable in constrained devices. The Nabaztag has only a small expressive repertoire compared with humanoid robots or animated characters. Yet the coordination of a few modalities can still produce a surprisingly rich interaction effect. A tilt of the ears combined with a brief pause and a colored light pulse can meaningfully alter how an utterance is perceived.

## 5. Personality and Emotional Expressivity

One of the design goals of the system is to avoid producing interchangeable AI endpoints. Each rabbit can be configured with its own personality prompt, allowing multiple devices to inhabit different tones and roles within the same household.

This matters because domestic objects are not used only for task completion. They are lived with. Their acceptability depends partly on affective consistency. A rabbit that is playful, gentle, ironic, or curious can create a more stable and memorable interaction pattern than a purely generic assistant.

The project therefore treats personality not as cosmetic prompt decoration, but as a structural property of the interaction model. The LLM prompt defines behavioral tone, humor, relation to household members, and expressive style. Structured expressive generation then operationalizes that personality across speech, motion, and light.

In this sense, emotional expressivity is not simulated through a high-fidelity face or a large motor repertoire. It is achieved through careful orchestration of limited but legible channels.

## 6. Domestic Use Cases

Although the implementation is exploratory, it already supports a range of realistic domestic scenarios.

### 6.1 Conversational Companion

The rabbit can participate in short conversational exchanges, maintain a limited working memory, and respond with coordinated speech and body language. This transforms the object from a notification endpoint into an interaction partner.

### 6.2 Ambient Interventions

The system can trigger randomized interventions within configurable time windows. These interventions are not merely spoken reminders. They can take the form of small performances combining utterance, ear movement, and light behavior. This supports a model of ambient companionship rather than on-demand only interaction.

### 6.3 Family and Shared-Space Presence

Because the device is physical, visible, and audible, it naturally operates in shared domestic spaces. Its interactions can be collectively perceived, unlike a private phone screen. This makes it particularly interesting for households with children, where the object can become part of shared routines and shared imagination.

## 7. Sustainability and Green IT Implications

A central argument of this work is that legacy devices can become relevant again through software-defined reconditioning.

Most AI hardware narratives focus on introducing new devices into the home: new assistants, new robots, new hubs, new wearables. By contrast, our project suggests a different path. Existing connected objects may already possess enough expressive and physical affordances to host meaningful AI interaction, provided that their software environment is renewed.

This perspective has several sustainability implications.

First, it extends device lifespan. A connected object from the early 2000s can still participate in contemporary AI scenarios without any hardware refit.

Second, it reduces replacement logic. Instead of treating legacy devices as obsolete by default, it reframes them as reusable interaction shells.

Third, it shifts innovation effort from manufacturing to software orchestration. This is important in Green IT terms because it encourages functional augmentation without requiring material renewal.

In that sense, the project is not only a technical prototype. It is also a design argument: sustainable innovation may increasingly depend on our ability to reinterpret existing objects rather than replace them.

## 8. Limitations

The current system also has clear limitations.

First, the physical device remains constrained by its original hardware capabilities. Expressivity is richer than plain voice output, but still bounded by the device's limited actuation and sensing repertoire.

Second, the current evaluation is exploratory rather than formal. The paper presents system design, implementation, and use cases, but does not yet include a controlled user study.

Third, legacy hardware can present reliability issues, especially in audio capture and long-term runtime behavior. These constraints are not incidental; they are part of the reality of software-defined reuse.

Fourth, structured expressive generation depends on prompt quality and reliable downstream execution. Coordination between generated intent and physical behavior can fail if one modality is unavailable or degraded.

## 9. Discussion

The reactivation of the Nabaztag raises a broader question for HCI and AI design: what kinds of objects should host AI in everyday life?

Our position is that embodied AI does not necessarily require new robots or visually complex devices. Simpler objects with strong identity, constrained expressivity, and clear domestic legibility may be better suited to many forms of everyday companionship.

The Nabaztag is especially interesting because its original design already encoded humor, familiarity, and lightness. By coupling that material identity with modern LLM-based behavior, we obtain an unusual hybrid: a legacy connected object acting as a contemporary embodied agent.

This also suggests a methodological direction for future work. Rather than designing embodied AI from scratch, researchers and practitioners might revisit forgotten connected objects as candidate AI interfaces. Many such objects already contain meaningful physical vocabularies that can be reinterpreted through software.

## 10. Conclusion

This paper presented a software-only approach for reviving a legacy IoT device as an embodied AI interface. Using the Nabaztag as a case study, we showed how contemporary LLM and TTS services can be integrated into an early connected object without hardware modification, enabling multimodal expressive behavior through speech, ear movement, and lighting.

We introduced structured expressive generation as a model for coordinating these output channels, and argued that such systems open a promising path both for richer domestic human-AI interaction and for sustainable innovation through software-defined reuse.

Far from being obsolete, legacy devices may become newly relevant when understood not as outdated products, but as existing physical hosts for modern intelligence.

## Acknowledgements

This draft accompanies the open source Nabaztag project and is intended as a basis for future academic submission. Author names, affiliations, figures, and references remain to be completed.
