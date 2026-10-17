import LegalDocument, { ContactLine } from "../../kitch/components/LegalDocument.js";

export const metadata = {
  title: "Privacy Policy · Kitch",
  description: "What Kitch collects, why, who processes it, how long it is kept, and how to delete it."
};

export default function PrivacyPage() {
  return (
    <LegalDocument
      title="Privacy Policy"
      intro="Kitch is an independent, personal project that helps one household plan meals, keep a pantry, prepare grocery carts and log nutrition. This policy explains what Kitch collects, why, who processes it on Kitch’s behalf, and the choices you have. Kitch is not affiliated with or endorsed by Google, Swiggy, Zepto or Blinkit."
    >
      <h2>What Kitch collects</h2>
      <ul>
        <li><strong>Your Google account basics.</strong> Your name, email address and Google account ID, received when you sign in with Google. Kitch never sees your Google password.</li>
        <li><strong>Household details you enter.</strong> Member names, timezone, household size, food preferences and anything you tell Kitch to remember, such as dislikes or favourite brands.</li>
        <li><strong>Kitchen data.</strong> Meal plans, recipes, pantry items, shopping lists and the messages you send to Kitch’s assistant.</li>
        <li><strong>Nutrition logs and photos.</strong> What each member ate, estimated calories and macros, daily goals, and photos of meals or your fridge. Because these describe what people eat, Kitch treats them as health-related information and handles them with extra care.</li>
        <li><strong>Grocery ordering data</strong>, only if you connect a grocery app such as Swiggy Instamart: the cart Kitch prepares, delivery addresses and payment options returned by that app, and the outcome of orders you approve. Kitch never sees or stores your card, UPI or bank details.</li>
        <li><strong>Technical data.</strong> A sign-in cookie and standard server logs (time, request path, errors) needed to run and secure the service. Kitch does not use advertising or analytics cookies.</li>
      </ul>

      <h2>Why Kitch uses it</h2>
      <p>Only to provide the features you use: planning meals, writing recipes, keeping the pantry and shopping list, preparing carts for your review, placing orders you approve, logging nutrition, remembering household preferences, and keeping the service secure. Kitch does not sell your data, show ads, or use your data to train AI models.</p>

      <h2>Your consent</h2>
      <p>Kitch asks for your explicit consent before you start, including for health-related nutrition logs. You can withdraw consent at any time by deleting your account (below). Withdrawing consent stops Kitch from processing your data from that point on.</p>
      <p>The household owner can add members by name, and can invite people to join with their own Google account. Everyone in a household can see and edit its shared meal plans, pantry and lists, and can open each member’s nutrition log. If you add someone by name, make sure they are happy for Kitch to keep their meals and nutrition logs. Only the owner can connect a grocery app and place orders.</p>

      <h2>Who processes data for Kitch</h2>
      <ul>
        <li><strong>Google</strong>: Sign in with Google; the Gemini API, which reads your messages and photos to generate plans, recipes and nutrition estimates; and Vertex AI Memory Bank, which stores remembered household preferences. Kitch uses Google’s paid API service, under which Google does not use prompts or responses to improve its products.</li>
        <li><strong>Supabase</strong>: the database that stores your household data.</li>
        <li><strong>Vercel</strong>: hosting for the Kitch website and server.</li>
        <li><strong>Swiggy</strong> (and any other grocery app you connect): receives the cart and order you approve. Orders, payments and delivery are governed by that app’s own terms and privacy policy.</li>
      </ul>
      <p>These providers may store or process data outside India, including in the United States. Each is bound by its own security and data-protection terms.</p>

      <h2>How long Kitch keeps it</h2>
      <ul>
        <li>Household data stays until you edit it, delete it, or delete your account.</li>
        <li>Grocery checkout reviews, payment status and order outcomes expire 24 hours after they were last used.</li>
        <li>Grocery app sign-in tokens are kept, encrypted, until you disconnect or they expire; expired connections are removed after 30 days.</li>
        <li>Server logs are kept only as long as needed to run and secure the service.</li>
      </ul>

      <h2>Deleting your data and your other rights</h2>
      <p>The household owner can delete everything at any time from <strong>Household settings → Delete account and data</strong>. This removes the household for everyone in it: every member’s plans, pantry, lists and nutrition logs, remembered preferences, and any connected grocery app tokens. A member who joined with their own account can instead <strong>leave the household</strong>, which deletes their sign-in and their own nutrition log. Data held by Swiggy or another grocery app about your orders is managed in that app.</p>
      <p>You can also ask to see a summary of your data, correct it, or delete it, and raise a grievance, by writing to <ContactLine />. Kitch aims to respond within 30 days. If you are not satisfied with the response, you may complain to the Data Protection Board of India.</p>

      <h2>Security</h2>
      <p>Kitch uses HTTPS everywhere, a signed and HttpOnly sign-in cookie, encrypted grocery app tokens, and household-level isolation on the server. No system is perfectly secure; if a breach affects your data, Kitch will tell you and the relevant authorities as the law requires.</p>

      <h2>Age</h2>
      <p>Kitch is only for people aged 18 or older. Do not use Kitch to log the meals of children.</p>

      <h2>Changes</h2>
      <p>If this policy changes materially, Kitch will ask you to review and accept the new version before you continue.</p>

      <h2>Contact</h2>
      <p>Questions or requests: <ContactLine />.</p>
    </LegalDocument>
  );
}
