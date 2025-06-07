import React, { useState } from "react";
import { styled } from "styled-components";
import { lighten, darken } from "polished";
import { getDivColor } from "../services/style";
import Tooltip from "./tooltip";

const TabContainer = styled.div`
  width: ${(props) => props.$width || "100%"};
  background-color: ${darken(0.05, getDivColor())};
  border-radius: 12px;
  padding: 10px 14px;
  color: #eee;
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  user-select: none;
`;

const TabHeader = styled.div`
  display: grid;
  grid-template-columns: repeat(${(props) => props.count}, 1fr);
  width: 100%;
  margin-bottom: 12px;
`;

const TabButton = styled.button`
  background-color: ${(props) =>
    props.active ? darken(0.15, getDivColor()) : darken(0.1, getDivColor())};
  color: #eee;
  padding: 10px 12px;
  border: none;
  border-radius: 8px 8px 0 0;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease;

  &:hover {
    background-color: ${(props) =>
      props.active ? darken(0.18, getDivColor()) : darken(0.2, getDivColor())};
  }

  &:focus {
    outline: 2px solid ${lighten(0.15, getDivColor())};
  }
`;

const TabContent = styled.div`
  background-color: ${darken(0.1, getDivColor())};
  padding: 16px;
  border-radius: 0 0 8px 8px;
`;

function TabView({ tabs, width, tooltip }) {
  const [activeTab, setActiveTab] = useState(tabs[0]?.key ?? 0);
  const [hoveredTab, setHoveredTab] = useState(null);

  const active = tabs.find((tab) => tab.key === activeTab);

  return (
    <TabContainer $width={width}>
      <TabHeader count={tabs.length}>
        {tabs.map((tab) => (
          <TabButton
            key={tab.key}
            active={tab.key === activeTab}
            onClick={() => setActiveTab(tab.key)}
            onMouseEnter={() => setHoveredTab(tab.key)}
            onMouseLeave={() => setHoveredTab(null)}
          >
            {tab.label}
            {tooltip && hoveredTab === tab.key && (
              <Tooltip visible>{tooltip(tab)}</Tooltip>
            )}
          </TabButton>
        ))}
      </TabHeader>
      <TabContent>{active?.content}</TabContent>
    </TabContainer>
  );
}

export default TabView;
