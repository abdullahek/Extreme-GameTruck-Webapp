import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { io } from "socket.io-client";
import Header from "../../components/Header/Header";
import "./Responses.css";

export default function Responses({ setIsAuthenticated }) {
  const [selectedContact, setSelectedContact] = useState(null);
  const [newMessage, setNewMessage] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [sidebarVisible, setSidebarVisible] = useState(false);
  
  // Progressive loading state
  const [contacts, setContacts] = useState([]);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [initialLoad, setInitialLoad] = useState(true);
  const [error, setError] = useState(null);
  
  const isLoadingRef = useRef(false);
  const messagesEndRef = useRef(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Initialize WebSocket connection
  const socket = useMemo(() => io('/', { autoConnect: true }), []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Progressive batch fetching function - fetches ALL batches in sequence
  // No useCallback needed since it's only called once from useEffect
  const fetchAllContacts = async () => {
    if (isLoadingRef.current) {
      console.log('⚠️ Already loading, skipping...');
      return;
    }
    
    isLoadingRef.current = true;
    setIsLoadingMore(true);
    setInitialLoad(true);
    
    console.log('🚀 Starting progressive contact loading...');
    
    let currentOffset = 0;
    const limit = 20;
    let hasMoreData = true;
    let totalFetched = 0;
    let batchNumber = 1;
    
    try {
      const token = localStorage.getItem("token");
      
      // Loop through all batches until no more data
      while (hasMoreData) {
        console.log(`📡 Fetching batch #${batchNumber} at offset=${currentOffset}`);
        
        const response = await fetch(`/api/contacts/preview?offset=${currentOffset}&limit=${limit}`, {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });

        if (response.status === 401) {
          localStorage.removeItem("token");
          localStorage.removeItem("user");
          setIsAuthenticated(false);
          navigate("/login");
          return;
        }

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`Failed to fetch contacts: ${response.status} ${errorText || response.statusText}`);
        }

        const data = await response.json();
        const contactsInBatch = data.contacts?.length || 0;
        
        console.log(`📥 Batch #${batchNumber} received: ${contactsInBatch} contacts (total so far: ${totalFetched + contactsInBatch}/${data.total})`);
        console.log(`   ℹ️ Backend returned hasMore=${data.hasMore} (offset=${data.offset}, limit=${data.limit})`);
        
        // Append new batch to existing contacts
        setContacts(prev => [...prev, ...(data.contacts || [])]);
        setTotal(data.total || 0);
        setHasMore(data.hasMore || false);
        
        // Update tracking variables
        totalFetched += contactsInBatch;
        currentOffset += contactsInBatch;
        hasMoreData = data.hasMore === true;
        batchNumber++;
        
        setOffset(currentOffset);
        
        console.log(`   📊 Progress: hasMoreData=${hasMoreData}, next offset will be ${currentOffset}`);
        
        // Small delay between batches to show progressive loading and avoid overwhelming the UI
        if (hasMoreData) {
          console.log(`   ⏳ Waiting 100ms before next batch...`);
          await new Promise(resolve => setTimeout(resolve, 100));
        } else {
          console.log(`   🏁 No more data - while loop will exit`);
        }
      }
      
      console.log(`✅ All contacts loaded! Total: ${totalFetched} contacts in ${batchNumber - 1} batches`);
      setInitialLoad(false);
      isLoadingRef.current = false;
      setIsLoadingMore(false);
      
    } catch (err) {
      console.error('❌ Error fetching contacts:', err);
      setError(err.message || 'Network error occurred');
      isLoadingRef.current = false;
      setIsLoadingMore(false);
      setInitialLoad(false);
    }
  };

  // Initial load - triggers progressive batch loading (empty deps = run ONLY once on mount)
  useEffect(() => {
    fetchAllContacts();
  }, []);

  // Fetch full messages for a specific contact (on-demand)
  const {
    data: fullMessagesData,
    isLoading: loadingMessages,
    isFetching: fetchingMessages,
    refetch: refetchMessages
  } = useQuery({
    queryKey: ['contact-messages', selectedContact?.contact_id],
    queryFn: async () => {
      if (!selectedContact) return null;
      
      const token = localStorage.getItem("token");
      const encodedContactId = encodeURIComponent(selectedContact.contact_id);
      const response = await fetch(`/api/messages/${encodedContactId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch messages');
      }

      const data = await response.json();
      return data.messages || [];
    },
    enabled: !!selectedContact,
    staleTime: 30000,
    cacheTime: 300000,
  });

  // Filter valid contacts
  const validContacts = useMemo(() => {
    return contacts.filter(contact => contact && contact.contact_name && contact.contact_phone);
  }, [contacts]);

  // Get current conversation messages
  const currentMessages = useMemo(() => {
    if (!selectedContact) return [];
    return fullMessagesData || [];
  }, [selectedContact, fullMessagesData]);

  // Send message mutation with optimistic updates
  const sendMessageMutation = useMutation({
    mutationFn: async ({ phone_number, message }) => {
      const token = localStorage.getItem("token");
      const response = await fetch("/api/messages/send", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ phone_number, message }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to send message');
      }

      return response.json();
    },
    onMutate: async ({ phone_number, message }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['contact-messages', selectedContact?.contact_id] });

      // Snapshot previous value
      const previousMessages = queryClient.getQueryData(['contact-messages', selectedContact?.contact_id]);

      // Optimistically update messages
      const optimisticMessage = {
        id: `temp-${Date.now()}`,
        text: message,
        type: 'outgoing',
        timestamp: new Date().toISOString(),
        status: 'sending'
      };

      queryClient.setQueryData(['contact-messages', selectedContact?.contact_id], (oldData) => {
        if (!oldData) return [optimisticMessage];
        return [...oldData, optimisticMessage];
      });

      // Also update the contact preview in local state
      setContacts(prevContacts => 
        prevContacts.map(contact => {
          if (contact.contact_id === selectedContact?.contact_id) {
            return {
              ...contact,
              last_message: {
                text: message,
                type: 'outgoing',
                timestamp: optimisticMessage.timestamp
              },
              last_message_time: optimisticMessage.timestamp,
              message_count: contact.message_count + 1
            };
          }
          return contact;
        })
      );

      setTimeout(() => scrollToBottom(), 50);

      return { previousMessages };
    },
    onSuccess: () => {
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: ['contact-messages', selectedContact?.contact_id] });
      queryClient.invalidateQueries({ queryKey: ['contacts-preview'] });
      setNewMessage("");
      console.log('📤 Message sent successfully - syncing with server');
    },
    onError: (error, variables, context) => {
      // Rollback on error
      if (context?.previousMessages) {
        queryClient.setQueryData(['contact-messages', variables.phone_number], context.previousMessages);
      }
      console.error("Error sending message:", error);
      alert(`Failed to send message: ${error.message}`);
    },
  });

  // Listen for real-time messages via WebSocket
  useEffect(() => {
    const handleNewMessage = ({ phone, message }) => {
      console.log('🔔 New message received via WebSocket:', { phone, message });

      // Invalidate queries to trigger refetch
      queryClient.invalidateQueries({ queryKey: ['contacts-preview'] });
      queryClient.invalidateQueries({ queryKey: ['contact-messages', phone] });

      // If this is the selected contact, also update the UI immediately
      if (selectedContact && selectedContact.contact_id === phone) {
        const formattedMessage = {
          ...message,
          text: message.text || message.message_text,
          type: message.type || message.message_type,
          timestamp: message.timestamp || message.created_at
        };

        queryClient.setQueryData(['contact-messages', selectedContact.contact_id], (oldData) => {
          if (!oldData) return [formattedMessage];
          return [...oldData, formattedMessage];
        });

        setTimeout(() => scrollToBottom(), 50);
      }
    };

    socket.on('new-message', handleNewMessage);
    return () => socket.off('new-message', handleNewMessage);
  }, [socket, queryClient, selectedContact]);

  // Join WebSocket rooms for contacts
  useEffect(() => {
    if (!validContacts || validContacts.length === 0) return;

    const joinedRooms = new Set();

    validContacts.forEach(contact => {
      const roomId = contact.contact_id;
      if (roomId && !joinedRooms.has(roomId)) {
        console.log('📱 Joining room:', roomId, 'for:', contact.contact_name);
        socket.emit('join', { phone: roomId });
        joinedRooms.add(roomId);
      }
    });

    return () => {
      joinedRooms.forEach(roomId => {
        console.log('📱 Leaving room:', roomId);
        socket.emit('leave', { phone: roomId });
      });
    };
  }, [validContacts, socket]);

  // Auto-scroll when messages change
  useEffect(() => {
    if (currentMessages.length > 0) {
      setTimeout(() => scrollToBottom(), 100);
    }
  }, [currentMessages]);

  const selectContact = (contact) => {
    setSelectedContact(contact);
    setSidebarVisible(false);
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !selectedContact || sendMessageMutation.isPending) return;

    sendMessageMutation.mutate({
      phone_number: selectedContact.contact_id,
      message: newMessage,
    });
  };

  const filteredContacts = validContacts.filter(
    (contact) =>
      contact.contact_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      contact.contact_phone.includes(searchTerm),
  );
  
  // Calculate remaining skeleton loaders to show
  const remainingToLoad = total - contacts.length;
  const skeletonsToShow = initialLoad ? 5 : (isLoadingMore && remainingToLoad > 0 ? Math.min(5, remainingToLoad) : 0);

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Skeleton Components
  const SkeletonConversationItem = () => (
    <div className="skeleton-conversation-item">
      <div className="skeleton-avatar"></div>
      <div className="skeleton-conversation-info">
        <div className="skeleton-conversation-name"></div>
        <div className="skeleton-conversation-phone"></div>
        <div className="skeleton-conversation-time"></div>
      </div>
      <div className="skeleton-message-count"></div>
    </div>
  );

  const SkeletonMessageList = () => (
    <div className="skeleton-message-list">
      <div className="skeleton-message incoming">
        <div className="skeleton-message-bubble"></div>
      </div>
      <div className="skeleton-message outgoing">
        <div className="skeleton-message-bubble"></div>
      </div>
      <div className="skeleton-message incoming">
        <div className="skeleton-message-bubble"></div>
      </div>
      <div className="skeleton-message outgoing">
        <div className="skeleton-message-bubble"></div>
      </div>
    </div>
  );

  if (error) {
    return (
      <div className="responses-container">
        <Header setIsAuthenticated={setIsAuthenticated} />
        <div className="loading-screen">
          <div className="error-message">
            <h2>Error loading contacts</h2>
            <p>{error}</p>
            <button onClick={() => {
              setError(null);
              setContacts([]);
              setOffset(0);
              setHasMore(true);
              fetchAllContacts();
            }}>
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="responses-container">
      <Header setIsAuthenticated={setIsAuthenticated} />

      <main className="responses-main">
        <div className="responses-layout">
          {/* Mobile Overlay */}
          <div
            className={`mobile-overlay ${sidebarVisible ? "active" : ""}`}
            onClick={() => setSidebarVisible(false)}
          ></div>

          {/* Conversations Sidebar */}
          <div
            className={`conversations-sidebar ${sidebarVisible ? "mobile-visible" : ""}`}
          >
            <div className="sidebar-header">
              <h3>💬 Conversations</h3>
              <div className="search-container">
                <input
                  type="text"
                  placeholder="Search contacts..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="search-input"
                />
              </div>
            </div>

            <div className="conversations-list">
              {initialLoad && contacts.length === 0 ? (
                <>
                  <SkeletonConversationItem />
                  <SkeletonConversationItem />
                  <SkeletonConversationItem />
                  <SkeletonConversationItem />
                  <SkeletonConversationItem />
                </>
              ) : filteredContacts.length === 0 && contacts.length === 0 && !isLoadingMore ? (
                <div className="empty-state">
                  <div className="empty-icon">📱</div>
                  <p>No conversations yet</p>
                  <small>
                    Messages will appear here when customers contact you
                  </small>
                </div>
              ) : (
                <>
                  {filteredContacts.map((contact, index) => (
                    <div
                      key={`${contact.contact_phone}-${index}`}
                      className={`conversation-item ${selectedContact?.contact_phone === contact.contact_phone ? "active" : ""}`}
                      onClick={() => selectContact(contact)}
                    >
                      <div className="conversation-avatar">
                        <div className="avatar-circle">
                          {contact.contact_name.charAt(0).toUpperCase()}
                        </div>
                        <div className="online-indicator"></div>
                      </div>
                      <div className="conversation-info">
                        <div className="conversation-name">
                          {contact.contact_name}
                        </div>
                        <div className="conversation-phone">
                          {contact.contact_phone}
                        </div>
                        <div className="last-message-time">
                          {formatTime(contact.last_message_time)}
                        </div>
                      </div>
                      <div className="message-count">
                        {contact.message_count}
                      </div>
                    </div>
                  ))}
                  {/* Show skeleton loaders for remaining contacts */}
                  {Array.from({ length: skeletonsToShow }).map((_, index) => (
                    <SkeletonConversationItem key={`skeleton-${index}`} />
                  ))}
                  {/* Show loading indicator at bottom when loading more */}
                  {isLoadingMore && remainingToLoad > 0 && (
                    <div style={{ textAlign: 'center', padding: '10px', color: '#888' }}>
                      Loading {remainingToLoad} more contacts...
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Chat Area */}
          <div className="chat-area">
            {selectedContact ? (
              <>
                <div className="chat-header">
                  <button
                    className="mobile-sidebar-toggle"
                    onClick={() => setSidebarVisible(!sidebarVisible)}
                  >
                    ☰
                  </button>
                  <div className="chat-contact-info">
                    <div className="chat-avatar">
                      {selectedContact.contact_name.charAt(0).toUpperCase()}
                    </div>
                    <div className="chat-contact-details">
                      <h4>{selectedContact.contact_name}</h4>
                      <p>{selectedContact.contact_phone}</p>
                    </div>
                  </div>
                  <div className="chat-actions">
                    <span className="live-indicator">🔴 LIVE</span>
                    {loadingMessages && !fullMessagesData && (
                      <div className="sync-loader">
                        <div className="sync-dot"></div>
                        <div className="sync-dot"></div>
                        <div className="sync-dot"></div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="messages-container">
                  {loadingMessages ? (
                    <SkeletonMessageList />
                  ) : (
                    <>
                      {currentMessages
                        .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
                        .map((msg, index) => {
                          let messageClass = 'message ';

                          if (msg.type === 'incoming' || msg.message_type === 'incoming') {
                            messageClass += 'incoming';
                          } else if (msg.type === 'outgoing' || msg.type === 'ai-response' || 
                                     msg.message_type === 'outgoing' || msg.message_type === 'ai-response') {
                            messageClass += 'outgoing';
                          } else {
                            messageClass += 'incoming';
                          }

                          const messageText = msg.text || msg.message_text || msg.content || '';
                          const messageTime = msg.timestamp || msg.created_at || new Date();

                          return (
                            <div key={`msg-${index}-${messageTime}`} className={messageClass}>
                              <div className="message-content">
                                <p>{messageText}</p>
                                <span className="message-time">
                                  {formatTime(messageTime)}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      <div ref={messagesEndRef} />
                    </>
                  )}
                </div>

                <form onSubmit={sendMessage} className="message-input-form">
                  <div className="input-container">
                    <input
                      type="text"
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      placeholder="Type your message..."
                      className="message-input"
                      disabled={sendMessageMutation.isPending}
                    />
                    <button
                      type="submit"
                      className={`send-button ${sendMessageMutation.isPending ? "sending" : ""}`}
                      disabled={!newMessage.trim() || sendMessageMutation.isPending}
                    >
                      {sendMessageMutation.isPending ? "⏳" : "🚀"}
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <div className="no-conversation-selected">
                <div className="select-conversation-content">
                  <div className="gaming-icon">🎮</div>
                  <h3>Select a Conversation</h3>
                  <p>
                    Choose a contact from the sidebar to view your gaming
                    conversation
                  </p>
                  <div className="gaming-features">
                    <div className="feature">🚛 Mobile Gaming</div>
                    <div className="feature">⚡ Real-time Chat</div>
                    <div className="feature">🤖 AI Assistant</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
