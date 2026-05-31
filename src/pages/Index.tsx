import { useState } from "react";
import Header from "@/components/Header";
import Hero from "@/components/Hero";
import Experience from "@/components/Experience";
import FitAssessment from "@/components/FitAssessment";
import AIChat from "@/components/AIChat";
import Footer from "@/components/Footer";

const Index = () => {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatInitialMessage, setChatInitialMessage] = useState<string | undefined>();

  const openChat = (initialMessage?: string) => {
    setChatInitialMessage(initialMessage);
    setIsChatOpen(true);
  };

  return (
    <div className="min-h-screen bg-background">
      <Header onOpenChat={() => openChat()} />
      <main>
        <Hero onOpenChat={() => openChat()} />
        <Experience onOpenChat={openChat} />
        <FitAssessment />
      </main>
      <Footer />
      <AIChat
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        initialMessage={chatInitialMessage}
      />
    </div>
  );
};

export default Index;
