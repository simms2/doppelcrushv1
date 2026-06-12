import Header from "@/components/Header";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Sticker } from "@/components/Stickers";

const faqs = [
  ["What's a DoppelCrush?", "It's that crush who looks just enough like you that everyone gets it. Same face card energy."],
  ["What's Chaos Mode?", "It's the opposite of your usual type. Same data, totally different result. Great for shaking up the feed."],
  ["Do you store my selfie?", "Your selfie is stored privately on your profile. We use it to compute a match signal. Delete your account and the photo is removed."],
  ["Is this app for 18+?", "Yes. You must confirm you're 18 or older during onboarding."],
  ["How do referrals work?", "Share your link from a match reveal. When a friend signs up, you both unlock extra daily matches."],
  ["Can I match with the same gender?", "Yes. Pick 'Women', 'Men', or 'Everyone' during onboarding — you can change it anytime."],
];

export default function FAQ() {
  return (
    <div className="crush-bg min-h-screen" data-testid="faq-page">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <Header />
        <div className="crush-frame mt-4 p-6 sm:p-10 relative">
          <Sticker kind="bolt" size={64} className="absolute -top-6 -right-4 rotate-12" color="#8a5cf6" />
          <h1 className="font-display text-5xl font-bold text-slate-900">FAQ</h1>
          <p className="mt-2 text-slate-600 font-body">Common questions, casually answered.</p>

          <Accordion type="single" collapsible className="mt-6">
            {faqs.map(([q, a], i) => (
              <AccordionItem value={`q-${i}`} key={q} className="border-b-2 border-slate-100">
                <AccordionTrigger className="font-display text-lg text-slate-900 hover:no-underline" data-testid={`faq-q-${i}`}>{q}</AccordionTrigger>
                <AccordionContent className="font-body text-slate-600">{a}</AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </div>
    </div>
  );
}
