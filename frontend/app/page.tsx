import { Hero } from "@/components/landing/hero";
import { BugPicker } from "@/components/landing/bug-picker";
import { HowItWorks } from "@/components/landing/how-it-works";
import { ProductShowcase } from "@/components/landing/product-showcase";
import { WhyVoice } from "@/components/landing/why-voice";
import { StatsStrip } from "@/components/landing/stats-strip";
import { WisprSection } from "@/components/landing/wispr-section";
import { Faq } from "@/components/landing/faq";
import { FinalCta } from "@/components/landing/final-cta";
import { SiteNav } from "@/components/landing/site-nav";
import { SiteFooter } from "@/components/landing/site-footer";

export default function Home() {
  return (
    <div id="top" className="flex min-h-screen flex-col">
      <SiteNav />

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6">
        <Hero />
        <BugPicker />
        <HowItWorks />
        <ProductShowcase />
        <WhyVoice />
        <StatsStrip />
        <WisprSection />
        <Faq />
        <FinalCta />
      </main>

      <SiteFooter />
    </div>
  );
}
