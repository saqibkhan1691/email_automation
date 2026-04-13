from colorama import Fore, Style
from .agents import Agents
from .tools.GmailTools import GmailToolsClass
from .state import GraphState, Email
import re


class Nodes:
    def __init__(self):
        self.agents = Agents()
        self.gmail_tools = GmailToolsClass()

    # ---------------------------------------------------
    # LOAD EMAILS
    # ---------------------------------------------------
    def load_new_emails(self, state: GraphState) -> GraphState:
        print(Fore.YELLOW + "Loading new emails...\n" + Style.RESET_ALL)

        recent_emails = self.gmail_tools.fetch_unanswered_emails()
        emails = [Email(**email) for email in recent_emails]

        state["emails"] = emails
        state["trials"] = 0
        state["writer_messages"] = []
        state["sendable"] = False

        return state

    # ---------------------------------------------------
    # CHECK IF EMAILS EXIST (node - returns state passthrough)
    # ---------------------------------------------------
    def check_new_emails(self, state: GraphState) -> GraphState:
        if not state.get("emails"):
            print(Fore.RED + "No new emails" + Style.RESET_ALL)
        else:
            print(Fore.GREEN + "New emails to process" + Style.RESET_ALL)
        return state

    # ---------------------------------------------------
    # ROUTE AFTER CHECK (for conditional edges - returns routing key)
    # ---------------------------------------------------
    def route_after_check(self, state: GraphState) -> str:
        return "empty" if not state.get("emails") else "process"

    # ---------------------------------------------------
    # CATEGORIZE EMAIL
    # ---------------------------------------------------
    def categorize_email(self, state: GraphState) -> GraphState:
        print(Fore.YELLOW + "Checking email category...\n" + Style.RESET_ALL)

        if not state.get("emails"):
            print("No emails found in state.")
            state["email_category"] = None
            return state

        current_email = state["emails"][-1]

        clean_text = re.sub("<.*?>", "", current_email.body)
        email_content = clean_text[:2500]

        result = self.agents.categorize_email.invoke({
            "email": email_content
        })

        category = result.category.value

        print(
            Fore.MAGENTA +
            f"Email category: {category}" +
            Style.RESET_ALL
        )

        state["email_category"] = category
        state["current_email"] = current_email

        return state

    # ---------------------------------------------------
    # ROUTING
    # ---------------------------------------------------
    def route_email_based_on_category(self, state: GraphState) -> str:
        print(Fore.YELLOW + "Routing email based on category...\n" + Style.RESET_ALL)

        category = state.get("email_category")

        if category == "product_enquiry":
            return "product related"
        elif category == "unrelated":
            return "unrelated"
        else:
            return "not product related"

    # ---------------------------------------------------
    # DESIGN RAG QUERY
    # ---------------------------------------------------
    def construct_rag_queries(self, state: GraphState) -> GraphState:
        print(Fore.YELLOW + "Designing RAG query...\n" + Style.RESET_ALL)

        if not state.get("current_email"):
            return state

        query_result = self.agents.design_rag_queries.invoke({
            "email": state["current_email"].body
        })

        state["rag_queries"] = query_result.queries
        return state

    # ---------------------------------------------------
    # RETRIEVE FROM RAG
    # ---------------------------------------------------
    def retrieve_from_rag(self, state: GraphState) -> GraphState:
        print(Fore.YELLOW + "Retrieving information from internal knowledge...\n" + Style.RESET_ALL)

        final_answer = ""

        for query in state.get("rag_queries", []):
            rag_result = self.agents.generate_rag_answer.invoke(query)
            final_answer += query + "\n" + rag_result + "\n\n"

        state["retrieved_documents"] = final_answer
        return state

    # ---------------------------------------------------
    # WRITE EMAIL
    # ---------------------------------------------------
    def write_draft_email(self, state: GraphState) -> GraphState:
        print(Fore.YELLOW + "Writing draft email...\n" + Style.RESET_ALL)

        if not state.get("current_email"):
            return state

        inputs = (
            f'# **EMAIL CATEGORY:** {state.get("email_category")}\n\n'
            f'# **EMAIL CONTENT:**\n{state["current_email"].body}\n\n'
            f'# **INFORMATION:**\n{state.get("retrieved_documents", "")}'
        )

        writer_messages = state.get("writer_messages", [])

        draft_result = self.agents.email_writer.invoke({
            "email_information": inputs,
            "history": writer_messages
        })

        email = draft_result.email
        trials = state.get("trials", 0) + 1

        writer_messages.append(f"**Draft {trials}:**\n{email}")

        state["generated_email"] = email
        state["trials"] = trials
        state["writer_messages"] = writer_messages

        return state

    # ---------------------------------------------------
    # VERIFY EMAIL
    # ---------------------------------------------------
    def verify_generated_email(self, state: GraphState) -> GraphState:
        print(Fore.YELLOW + "Verifying generated email...\n" + Style.RESET_ALL)

        if not state.get("generated_email"):
            return state

        review = self.agents.email_proofreader.invoke({
            "initial_email": state["current_email"].body,
            "generated_email": state["generated_email"],
        })

        # Debug: log proofreader decision
        feedback_preview = review.feedback[:100] + "..." if len(review.feedback) > 100 else review.feedback
        print(Fore.CYAN + f"[Proofreader] send={review.send}, feedback={feedback_preview}" + Style.RESET_ALL)

        writer_messages = state.get("writer_messages", [])
        writer_messages.append(f"**Proofreader Feedback:**\n{review.feedback}")

        state["sendable"] = review.send
        state["writer_messages"] = writer_messages

        return state

    # ---------------------------------------------------
    # REWRITE CONTROL (returns routing key: "send", "rewrite", or "stop")
    # ---------------------------------------------------
    def must_rewrite(self, state: GraphState) -> str:
        if not state.get("emails"):
            print("No emails left to process.")
            return "stop"

        if state.get("sendable"):
            print("Email approved. Removing from queue.")
            return "send"

        if state.get("trials", 0) >= 3:
            print("Max rewrite attempts reached. Saving draft anyway.")
            return "send"

        print("Email is not good, rewriting...")
        return "rewrite"

    # ---------------------------------------------------
    # SEND / DRAFT
    # ---------------------------------------------------
    def create_draft_response(self, state: GraphState) -> GraphState:
        print(Fore.YELLOW + "Creating draft email...\n" + Style.RESET_ALL)

        if state.get("generated_email"):
            self.gmail_tools.create_draft_reply(
                state["current_email"],
                state["generated_email"]
            )
            # Label thread as AI Handled (product/support - draft created)
            self.gmail_tools.apply_ai_handled_label(state["current_email"].id)
            # Remove processed email from queue before checking for more
            if state.get("emails"):
                state["emails"].pop()

        state["retrieved_documents"] = ""
        state["trials"] = 0
        return state

    def send_email_response(self, state: GraphState) -> GraphState:
        print(Fore.YELLOW + "Sending email...\n" + Style.RESET_ALL)

        if state.get("generated_email"):
            self.gmail_tools.send_reply(
                state["current_email"],
                state["generated_email"]
            )

        state["retrieved_documents"] = ""
        state["trials"] = 0
        return state

    # ---------------------------------------------------
    # SKIP UNRELATED
    # ---------------------------------------------------
    def skip_unrelated_email(self, state: GraphState) -> GraphState:
        print("Skipping unrelated email (applying 'Review Later' label)...\n")

        if state.get("emails"):
            current_email = state["emails"][-1]
            # Label as Review Later - not spam, user can see and reply when ready
            self.gmail_tools.apply_review_later_label(current_email.id)
            state["emails"].pop()

        return state