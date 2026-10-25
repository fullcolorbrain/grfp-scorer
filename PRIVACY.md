# GRFP Scorer — Privacy Notice

*Version 2026-10*

## What is collected, and when

**At registration (first launch, after you accept the license).**
The application sends to the author:

| Field | Why |
|---|---|
| Name | To count distinct users |
| Email address | To count distinct users and, rarely, to announce an updated version |
| Institution | To count how many institutions use the tool |
| Operating system, architecture, and app version | To know which builds are in use |
| A random installation identifier | To avoid counting the same installation twice |

**After each scoring run — only if you opted in.**
The installation identifier, the type of statement scored (personal or research), the
scores (ten-principle total, four-item score, disease-centrality flag), which backend and
model read it, the statement's word count, and the app version. No text from your
statement, no file names, and no student names are sent.

**Never sent to the author:** the text of your statement, the file you scored, the
per-principle evidence quotes, your API key, or anything else in the app.

**Sent to Anthropic, only if you use the Claude backend:** the text of your statement
and the rubric, under your own API key. This is governed by Anthropic's terms and
privacy policy, not by this notice. The Ollama and offline backends send nothing
anywhere.

## Where it goes and how it is used

Registration and usage events are stored in a private spreadsheet controlled by the
author. They are used only to (1) count users and institutions, in aggregate, for
reporting on the reach of the tool, and (2) occasionally notify registered users of a
new version. They are not sold, shared with third parties, or used for advertising.
Aggregate counts (for example, "used at 40 institutions in 6 countries") may be published;
individual names and emails are not.

## Your choices

- Registration is required to use the application, because the author needs to count
  users; the usage ping after each run is optional and off unless you tick the box.
- To have your registration record deleted, email the author (address on
  https://fullcolorbrain.com) from the registered address and it will be removed.
- Everything the app stores on your own computer is in one folder in your home
  directory (`~/.grfp_scorer/`). Deleting that folder removes your API key, settings,
  and scoring history.

## Children

The application is intended for graduate and advanced undergraduate students and is not
directed at children under 16.
